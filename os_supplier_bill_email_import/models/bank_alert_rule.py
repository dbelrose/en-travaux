# -*- coding: utf-8 -*-
"""
bank.alert.email.rule — Règle de parsing d'alerte bancaire par email.

Flux :
  Email d'alerte banque (ex : Marara Paiement / OPT)
    → Extraction des lignes d'opérations (date, sens, montant, libellé)
      → Création de account.bank.statement.line dans le journal bancaire
        → Rapprochement automatique (optionnel) avec les pièces ouvertes
"""

import re
import logging
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankAlertEmailRule(models.Model):
    """
    Règle de parsing pour les emails d'alerte bancaire.

    Ces emails notifient d'opérations débitrices ou créditrices sur un compte
    bancaire (prélèvements, virements, paiements CB…). Le module extrait
    chaque opération et crée les lignes de relevé bancaire correspondantes
    dans Odoo, prêtes à être rapprochées.

    Différences avec supplier.email.rule :
      • Pas de facture fournisseur — on crée des account.bank.statement.line
      • Plusieurs opérations par email (regex multi-occurrence)
      • Rapprochement automatique possible contre les pièces ouvertes
    """

    _name = 'bank.alert.email.rule'
    _description = "Règle de parsing alerte bancaire"
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.alias.mixin']

    # ── Identité ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nom de la règle',
        required=True,
        help="Ex : Alerte Marara Paiement XPF, OPT Banque EUR"
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Identification de l'email entrant ─────────────────────────────────────
    sender_email_pattern = fields.Char(
        string="Pattern expéditeur (regex)",
        help="Regex sur l'adresse expéditeur.\n"
             "Ex : no-reply@mararapaiement\\.pf"
    )
    subject_pattern = fields.Char(
        string="Pattern sujet (regex, optionnel)",
        help="Si renseigné, le sujet de l'email doit correspondre.\n"
             "Ex : Alerte sur votre compte"
    )

    # ── Journal bancaire ──────────────────────────────────────────────────────
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal bancaire',
        required=True,
        domain=[('type', '=', 'bank')],
        help="Journal de banque dans lequel les lignes de relevé seront créées."
    )
    currency_code = fields.Char(
        string='Code devise',
        default='XPF',
        help="Ex : XPF, EUR, USD. Doit correspondre à la devise du journal."
    )

    # ── Regex d'extraction ────────────────────────────────────────────────────
    regex_account_number = fields.Char(
        string='Regex n° de compte (optionnel)',
        help="Regex avec un groupe capturant le numéro de compte bancaire "
             "pour vérifier que l'alerte concerne le bon compte.\n"
             "Ex : compte\\s+\\w+\\s+\\(([\\w\\-]+)\\s+XPF\\)"
    )
    expected_account_number = fields.Char(
        string='N° de compte attendu',
        help="Si renseigné, l'email est rejeté si le numéro de compte "
             "extrait ne correspond pas à cette valeur."
    )
    regex_transaction = fields.Char(
        string='Regex ligne d\'opération',
        required=True,
        help="Regex Python avec 3 ou 4 groupes capturants :\n"
             "  groupe 1 → date (JJ/MM/AAAA)\n"
             "  groupe 2 → sens : 'débit' ou 'crédit' (ou directement le signe)\n"
             "  groupe 3 → montant (chiffres + espaces + virgule/point)\n"
             "  groupe 4 → libellé de l'opération\n\n"
             "Exemple Marara Paiement :\n"
             "Le\\s+(\\d{2}/\\d{2}/\\d{4}),\\s+"
             "(d[ée]bit|cr[ée]dit)\\s+de\\s+"
             "([\\d\\s\\u00a0\\u202f,\\.]+?)\\s*(?:XPF|FCFP)\\s+"
             "([A-Z][A-Z\\s]+?)(?=\\s*[,<\\n]|$)"
    )

    # ── Rapprochement automatique ─────────────────────────────────────────────
    auto_reconcile = fields.Boolean(
        string='Rapprochement automatique',
        default=False,
        help="Tente de rapprocher chaque ligne de relevé avec une pièce "
             "comptable ouverte dont le montant correspond exactement.\n"
             "Recommandé uniquement pour les prélèvements à montant fixe "
             "(abonnements, loyers…)."
    )
    reconcile_partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur pour le rapprochement',
        help="Si renseigné, le rapprochement est limité aux pièces de ce "
             "fournisseur. Laissez vide pour chercher sur tous les tiers."
    )
    reconcile_label_filter = fields.Char(
        string='Filtre libellé pour rapprochement (regex)',
        help="Si renseigné, seules les opérations dont le libellé correspond "
             "à cette regex seront rapprochées automatiquement.\n"
             "Ex : PRELEVEMENT (pour ne rapprocher que les prélèvements, "
             "pas les virements)"
    )

    # ── Statistiques ──────────────────────────────────────────────────────────
    statement_line_count = fields.Integer(
        string='Lignes créées',
        compute='_compute_statement_line_count'
    )
    last_import_date = fields.Datetime(string='Dernier import', readonly=True)
    last_import_result = fields.Char(string='Résultat dernier import', readonly=True)

    def _compute_statement_line_count(self):
        for rule in self:
            rule.statement_line_count = self.env['account.bank.statement.line'].search_count([
                ('journal_id', '=', rule.journal_id.id),
                ('narration', 'ilike', "Règle '%s'" % rule.name),
            ])

    # ── mail.alias.mixin ──────────────────────────────────────────────────────

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values.update({
            'alias_model_id': self.env['ir.model']._get(self._name).id,
            'alias_defaults': repr({'rule_id': self.id}),
        })
        return values

    # ── Point d'entrée : réception automatique d'un email ────────────────────

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Appelé par fetchmail lorsqu'un email arrive sur l'alias."""
        custom_values = custom_values or {}
        rule_id = custom_values.get('rule_id')
        rule = self.browse(rule_id) if rule_id else \
            self._detect_rule_from_sender(msg_dict.get('email_from', ''))

        if not rule:
            _logger.warning(
                "bank_alert message_new: aucune règle pour '%s'.",
                msg_dict.get('email_from', '?')
            )
            return super().message_new(msg_dict, custom_values)

        # Vérification expéditeur
        if rule.sender_email_pattern:
            sender = msg_dict.get('email_from', '')
            if not re.search(rule.sender_email_pattern, sender, re.IGNORECASE):
                rule._set_last_import_result(
                    False, "⛔ Expéditeur '%s' refusé." % sender
                )
                return super().message_new(msg_dict, custom_values)

        from .supplier_email_rule import SupplierEmailRule
        body_text = SupplierEmailRule._extract_text_from_msg_dict(msg_dict)

        if not body_text:
            rule._set_last_import_result(False, "❌ Corps de l'email vide.")
            return super().message_new(msg_dict, custom_values)

        try:
            results = rule.process_bank_alert(body_text)
            created = sum(1 for r in results if r.get('created'))
            duplicates = sum(1 for r in results if not r.get('created') and not r.get('error'))
            errors = sum(1 for r in results if r.get('error'))
            status = "✔ %d créée(s)" % created
            if duplicates:
                status += " / ⚠ %d doublon(s)" % duplicates
            if errors:
                status += " / ❌ %d erreur(s)" % errors
            rule._set_last_import_result(bool(created), status)
        except UserError as e:
            rule._set_last_import_result(False, "❌ " + str(e))

        return super().message_new(msg_dict, custom_values)

    # ── Détection de règle ────────────────────────────────────────────────────

    @api.model
    def _detect_rule_from_sender(self, sender_email):
        for rule in self.search([('active', '=', True)]):
            if rule.sender_email_pattern and re.search(
                rule.sender_email_pattern, sender_email, re.IGNORECASE
            ):
                return rule
        return None

    def _set_last_import_result(self, success, message):
        self.ensure_one()
        self.sudo().write({
            'last_import_date': fields.Datetime.now(),
            'last_import_result': message,
        })
        _logger.info("[%s] %s", self.name, message)

    # ── Parsing ───────────────────────────────────────────────────────────────

    def _clean_amount(self, raw):
        """Convertit une chaîne de montant en float positif."""
        cleaned = re.sub(r'[\s\u00a0\u202f]', '', raw)
        cleaned = cleaned.replace(',', '.')
        try:
            return abs(float(cleaned))
        except ValueError:
            raise UserError(
                _("Impossible de convertir le montant '%s' en nombre.") % raw
            )

    def _parse_transactions(self, body_text):
        """
        Extrait toutes les opérations bancaires du corps de l'email.

        Chaque correspondance de regex_transaction donne un dict :
          {
            'date'   : date,
            'amount' : float (positif = crédit, négatif = débit),
            'label'  : str,
            'raw_direction': str  ('débit' | 'crédit' | ...),
          }

        Returns:
            list of dict
        """
        self.ensure_one()
        if not self.regex_transaction:
            raise UserError(_("Regex de transaction non configurée (règle '%s').") % self.name)

        # Vérification du n° de compte si configuré
        if self.regex_account_number and self.expected_account_number:
            m = re.search(self.regex_account_number, body_text, re.IGNORECASE)
            if m:
                found_account = m.group(1).strip()
                if found_account != self.expected_account_number.strip():
                    raise UserError(_(
                        "Règle '%s' : n° de compte '%s' ne correspond pas "
                        "au compte attendu '%s'."
                    ) % (self.name, found_account, self.expected_account_number))
            else:
                _logger.warning(
                    "_parse_transactions [%s]: n° de compte non trouvé dans l'email.",
                    self.name
                )

        transactions = []
        try:
            for m in re.finditer(
                self.regex_transaction, body_text, re.IGNORECASE | re.MULTILINE
            ):
                groups = m.groups()
                if len(groups) < 4:
                    raise UserError(_(
                        "La regex de transaction doit avoir au moins 4 groupes "
                        "(date, sens, montant, libellé). Règle : '%s'"
                    ) % self.name)

                date_str = groups[0].strip()
                direction = groups[1].strip().lower()
                amount_raw = groups[2].strip()
                label = re.sub(r'\s+', ' ', groups[3].strip())

                # Parse date
                try:
                    tx_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                except ValueError:
                    _logger.warning(
                        "_parse_transactions: date '%s' ignorée (format inattendu).",
                        date_str
                    )
                    continue

                # Parse montant
                try:
                    amount = self._clean_amount(amount_raw)
                except UserError:
                    _logger.warning(
                        "_parse_transactions: montant '%s' ignoré.", amount_raw
                    )
                    continue

                # Signe : débit = négatif (sortie de trésorerie)
                is_debit = re.search(r'd[ée]bit', direction)
                signed_amount = -amount if is_debit else amount

                transactions.append({
                    'date': tx_date,
                    'amount': signed_amount,
                    'label': label,
                    'raw_direction': direction,
                })

        except re.error as exc:
            raise UserError(
                _("Regex de transaction invalide (règle '%s') : %s") % (self.name, exc)
            )

        _logger.info(
            "_parse_transactions [%s] : %d opération(s) extraite(s).",
            self.name, len(transactions)
        )
        return transactions

    # ── Création des lignes de relevé ─────────────────────────────────────────

    def process_bank_alert(self, body_text):
        """
        Point d'entrée principal : parse l'email et crée les lignes de relevé.

        Args:
            body_text (str) : corps texte de l'email d'alerte

        Returns:
            list of dict — résultats par opération :
              {'tx': dict, 'created': bool, 'stmt_line': record|None,
               'reconciled': bool, 'error': str|None}
        """
        self.ensure_one()
        transactions = self._parse_transactions(body_text)
        if not transactions:
            raise UserError(
                _("Aucune opération trouvée dans l'email (règle '%s'). "
                  "Vérifiez la regex de transaction.") % self.name
            )

        # Devise
        currency = self.env['res.currency'].search(
            [('name', '=', self.currency_code)], limit=1
        )
        if not currency:
            raise UserError(_("Devise '%s' introuvable.") % self.currency_code)

        results = []
        for tx in transactions:
            result = self._create_statement_line(tx, currency)
            results.append(result)

        return results

    def _build_dedup_ref(self, tx):
        """
        Construit une référence de déduplication unique par opération.
        Format : RULE_ID|DATE|AMOUNT|LABEL
        """
        return "%d|%s|%.2f|%s" % (
            self.id,
            tx['date'].strftime('%Y%m%d'),
            tx['amount'],
            tx['label'][:50],
        )

    def _create_statement_line(self, tx, currency):
        """
        Crée une ligne de relevé bancaire pour une opération.

        En cas de doublon (même règle + date + montant + libellé), la ligne
        existante est retournée sans création.

        Returns:
            dict : {'tx', 'created', 'stmt_line', 'reconciled', 'error'}
        """
        self.ensure_one()
        StmtLine = self.env['account.bank.statement.line']
        dedup_ref = self._build_dedup_ref(tx)

        # Déduplication
        existing = StmtLine.search([
            ('journal_id', '=', self.journal_id.id),
            ('narration', 'like', dedup_ref),
        ], limit=1)
        if existing:
            _logger.info(
                "_create_statement_line [%s] : doublon ignoré (%s).",
                self.name, dedup_ref
            )
            return {
                'tx': tx, 'created': False,
                'stmt_line': existing, 'reconciled': False,
                'error': None,
            }

        # Narration interne (contient la ref de dédup)
        narration = "Règle '%s' | %s" % (self.name, dedup_ref)

        try:
            stmt_line = StmtLine.create({
                'journal_id': self.journal_id.id,
                'date': tx['date'],
                'payment_ref': tx['label'],
                'amount': tx['amount'],
                'foreign_currency_id': False,
                'narration': narration,
            })
        except Exception as exc:
            _logger.error(
                "_create_statement_line [%s] : erreur création — %s", self.name, exc
            )
            return {
                'tx': tx, 'created': False,
                'stmt_line': None, 'reconciled': False,
                'error': str(exc),
            }

        _logger.info(
            "_create_statement_line [%s] : créée — %s %.0f %s",
            self.name, tx['date'], tx['amount'], self.currency_code
        )

        reconciled = False
        if self.auto_reconcile:
            reconciled = self._try_auto_reconcile(stmt_line, tx)

        return {
            'tx': tx, 'created': True,
            'stmt_line': stmt_line, 'reconciled': reconciled,
            'error': None,
        }

    # ── Rapprochement automatique ─────────────────────────────────────────────

    def _try_auto_reconcile(self, stmt_line, tx):
        """
        Tente de rapprocher la ligne de relevé avec une pièce comptable ouverte.

        Stratégie :
          1. Filtrer par libellé si reconcile_label_filter est renseigné
          2. Chercher les lignes account.move.line ouvertes avec
             amount_residual = abs(tx['amount']) sur un compte fournisseur
             (ou client pour les crédits)
          3. Si une correspondance unique est trouvée : rapprocher
          4. Sinon : laisser en attente (rapprochement manuel)

        Returns:
            bool — True si rapprochement effectué
        """
        self.ensure_one()

        # Filtre libellé
        if self.reconcile_label_filter:
            if not re.search(self.reconcile_label_filter, tx['label'], re.IGNORECASE):
                _logger.debug(
                    "_try_auto_reconcile [%s] : libellé '%s' filtré, pas de rapprochement.",
                    self.name, tx['label']
                )
                return False

        # Pour un débit bancaire, on cherche un compte fournisseur ouvert
        is_debit = tx['amount'] < 0
        account_types = (
            ['liability_payable'] if is_debit else ['asset_receivable']
        )
        amount_to_match = abs(tx['amount'])

        domain = [
            ('account_id.account_type', 'in', account_types),
            ('reconciled', '=', False),
            ('move_id.state', '=', 'posted'),
            ('amount_residual', '=', amount_to_match),
        ]
        if self.reconcile_partner_id:
            domain.append(('partner_id', '=', self.reconcile_partner_id.id))

        matching_lines = self.env['account.move.line'].search(domain)

        if len(matching_lines) != 1:
            _logger.info(
                "_try_auto_reconcile [%s] : %.0f %s → %d correspondance(s), "
                "rapprochement manuel requis.",
                self.name, amount_to_match, self.currency_code, len(matching_lines)
            )
            return False

        # Une correspondance unique : rapprochement
        try:
            move_line = matching_lines
            # Récupérer la ligne de contrepartie (compte de suspense) de la
            # ligne de relevé pour la rapprocher avec la ligne fournisseur
            suspense_line = stmt_line.move_id.line_ids.filtered(
                lambda l: l.account_id.account_type in account_types
                and not l.reconciled
            )
            if not suspense_line:
                # Fallback : chercher sur le compte de tiers (payable/receivable)
                # via la méthode de rapprochement standard de la ligne de relevé
                _logger.warning(
                    "_try_auto_reconcile [%s] : ligne de suspense introuvable "
                    "pour %s.", self.name, stmt_line.payment_ref
                )
                return False

            to_reconcile = suspense_line | move_line
            to_reconcile.reconcile()

            _logger.info(
                "_try_auto_reconcile [%s] : ✔ rapprochement %s ↔ %s",
                self.name,
                stmt_line.payment_ref,
                matching_lines.move_id.name
            )
            return True

        except Exception as exc:
            _logger.error(
                "_try_auto_reconcile [%s] : erreur rapprochement — %s",
                self.name, exc
            )
            return False

    # ── Actions UI ────────────────────────────────────────────────────────────

    def action_view_statement_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'domain': [
                ('journal_id', '=', self.journal_id.id),
                ('narration', 'ilike', "Règle '%s'" % self.name),
            ],
            'view_mode': 'list,form',
            'name': _('Relevé bancaire — %s') % self.name,
        }

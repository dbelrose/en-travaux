# -*- coding: utf-8 -*-
import re
import logging
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SupplierEmailRule(models.Model):
    """
    Règle de parsing d'email fournisseur.

    Chaque règle est également un **alias email** : lorsque le serveur de
    messagerie entrant (fetchmail) reçoit un email à l'adresse de l'alias,
    Odoo appelle automatiquement `message_new()` qui déclenche le parsing
    et la création de la facture fournisseur.

    Flux automatique :
        Serveur IMAP/POP3 (fetchmail.server)
            → routing Odoo (mail.alias)
                → message_new() sur cette règle
                    → _parse_email_body()
                        → create_vendor_bill()
                            → account.move (facture brouillon)
    """
    _name = 'supplier.email.rule'
    _description = 'Règle de parsing email fournisseur'
    _order = 'sequence, name'

    # Héritage mail.thread pour la gestion des alias et du chatter
    _inherit = ['mail.thread', 'mail.alias.mixin']

    # ── Identité ─────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Nom de la règle',
        required=True,
        help="Ex : EDT Électricité, OPT Téléphonie, Syndic Copropriété"
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Identification de l'email entrant ────────────────────────────────────
    sender_email_pattern = fields.Char(
        string="Pattern expéditeur (regex)",
        help="Regex sur l'adresse expéditeur pour vérifier l'origine de l'email.\n"
             "Sécurité : si l'expéditeur ne correspond pas, l'email est ignoré.\n"
             "Ex : efacture@.*edt\\.engie\\.pf"
    )
    subject_pattern = fields.Char(
        string="Pattern sujet (regex, optionnel)",
        help="Regex optionnelle sur le sujet de l'email."
    )

    # ── Regex d'extraction ───────────────────────────────────────────────────
    regex_invoice_number = fields.Char(
        string='Regex n° facture',
        required=True,
        help="Ex : facture\\s+(\\S+)\\s+du"
    )
    regex_invoice_date = fields.Char(
        string='Regex date (JJ/MM/AAAA)',
        required=True,
        help="Ex : du\\s+(\\d{2}/\\d{2}/\\d{4})"
    )
    regex_amount = fields.Char(
        string='Regex montant',
        required=True,
        help="Ex : montant de ([\\d\\s\\u00a0\\u202f,\\.]+?)\\s*(?:FCFP|EUR|XPF)"
    )
    regex_contract = fields.Char(
        string='Regex n° contrat',
        required=True,
        help="Ex : contrat\\s+([\\w\\-]+)"
    )
    currency_code = fields.Char(
        string='Code devise',
        default='XPF',
    )

    # ── Lien produit / analytique ─────────────────────────────────────────────
    product_attribute_name = fields.Char(
        string='Nom attribut produit',
        required=True,
        default='N° de contrat EDT',
        help="Nom de l'attribut produit stockant le numéro de contrat."
    )

    # ── Comptabilité ──────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Fournisseur',
        required=True,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal achats',
        domain=[('type', '=', 'purchase')],
    )
    account_id = fields.Many2one(
        'account.account',
        string='Compte de charge',
        required=True,
    )
    analytic_plan_id = fields.Many2one(
        'account.analytic.plan',
        string='Plan analytique',
    )

    # ── Statistiques de suivi ─────────────────────────────────────────────────
    bill_count = fields.Integer(
        string='Factures créées',
        compute='_compute_bill_count',
    )
    last_import_date = fields.Datetime(
        string='Dernier import',
        readonly=True,
    )
    last_import_result = fields.Char(
        string='Résultat dernier import',
        readonly=True,
    )
    def _compute_bill_count(self):
        for rule in self:
            rule.bill_count = self.env['account.move'].search_count([
                ('move_type', '=', 'in_invoice'),
                ('partner_id', '=', rule.partner_id.id),
                ('narration', 'ilike', "Règle '%s'" % rule.name),
            ])

    # ── mail.alias.mixin — configuration de l'alias ──────────────────────────

    def _alias_get_creation_values(self):
        """
        Valeurs par défaut pour l'alias email créé automatiquement
        à la création de chaque règle.

        L'alias route les emails entrants directement vers message_new()
        de cette règle (record), en lui passant rule_id dans alias_defaults.
        """
        values = super()._alias_get_creation_values()
        values.update({
            'alias_model_id': self.env['ir.model']._get(self._name).id,
            'alias_defaults': repr({'rule_id': self.id}),
        })
        return values

    # ── Point d'entrée : réception automatique d'un email ────────────────────

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        Appelé automatiquement par Odoo (mail.thread) lorsqu'un email
        arrive sur l'alias de cette règle via fetchmail.

        msg_dict (dict) fourni par Odoo :
            email_from  : adresse expéditeur
            subject     : sujet
            body        : corps HTML
            body_text   : corps texte brut (si disponible)
            date        : date de réception
            attachments : liste de (filename, content_bytes, mimetype)

        custom_values (dict) fourni par l'alias :
            rule_id : id de la règle (positionné dans alias_defaults)
        """
        custom_values = custom_values or {}
        rule_id = custom_values.get('rule_id')

        # Résolution de la règle
        if rule_id:
            rule = self.browse(rule_id)
        else:
            # Fallback : détection par pattern expéditeur
            rule = self._detect_rule_from_sender(
                msg_dict.get('email_from', '')
            )

        if not rule:
            _logger.warning(
                "message_new: aucune règle pour l'expéditeur '%s'. Ignoré.",
                msg_dict.get('email_from', '?')
            )
            return super().message_new(msg_dict, custom_values)

        # Vérification de sécurité : pattern expéditeur
        if rule.sender_email_pattern:
            sender = msg_dict.get('email_from', '')
            if not re.search(
                rule.sender_email_pattern, sender, re.IGNORECASE
            ):
                _logger.warning(
                    "message_new: expéditeur '%s' refusé par la règle '%s'.",
                    sender, rule.name
                )
                rule._set_last_import_result(
                    False,
                    "⛔ Email refusé — expéditeur '%s' non autorisé." % sender
                )
                return super().message_new(msg_dict, custom_values)

        # Extraction du corps texte
        body_text = rule._extract_text_from_msg_dict(msg_dict)
        if not body_text:
            _logger.error(
                "message_new: corps texte vide (sujet: '%s').",
                msg_dict.get('subject', '?')
            )
            rule._set_last_import_result(
                False, "❌ Corps de l'email vide ou illisible."
            )
            return super().message_new(msg_dict, custom_values)

        # Parsing du corps
        try:
            parsed = rule._parse_email_body(body_text)
        except UserError as e:
            _logger.error("message_new: erreur parsing — %s", str(e))
            rule._set_last_import_result(False, "❌ " + str(e))
            return super().message_new(msg_dict, custom_values)

        # Création de la facture
        try:
            move, created = rule.create_vendor_bill(parsed)
            if created:
                status = (
                    "✔ Facture %s créée — Contrat %s — %.0f %s"
                    % (
                        parsed['invoice_number'],
                        parsed['contract_number'],
                        parsed['amount'],
                        rule.currency_code,
                    )
                )
            else:
                status = (
                    "⚠ Doublon ignoré : facture %s déjà présente."
                    % parsed['invoice_number']
                )
            rule._set_last_import_result(created, status)
        except UserError as e:
            _logger.error(
                "message_new: erreur création facture — %s", str(e)
            )
            rule._set_last_import_result(False, "❌ " + str(e))

        return super().message_new(msg_dict, custom_values)

    def _set_last_import_result(self, success, message):
        """Met à jour les champs de suivi sur la règle (sudo pour éviter
        les problèmes de droits dans le contexte mail)."""
        self.ensure_one()
        self.sudo().write({
            'last_import_date': fields.Datetime.now(),
            'last_import_result': message,
        })
        _logger.info("[%s] %s", self.name, message)

    @api.model
    def _detect_rule_from_sender(self, sender_email):
        """Détecte la règle active correspondant à l'adresse expéditeur."""
        for rule in self.search([('active', '=', True)]):
            if rule.sender_email_pattern and re.search(
                rule.sender_email_pattern, sender_email, re.IGNORECASE
            ):
                return rule
        return None

    @staticmethod
    def _extract_text_from_msg_dict(msg_dict):
        """
        Extrait le meilleur corps texte depuis le dict message Odoo 17.
        Priorité : body_text (brut) > body (HTML nettoyé).
        """
        import quopri

        body_text = msg_dict.get('body_text') or ''
        if body_text.strip():
            # Décoder le quoted-printable si nécessaire
            if '=E2=' in body_text or '=C3=' in body_text or '=AF' in body_text:
                try:
                    body_text = quopri.decodestring(
                        body_text.encode('latin-1')
                    ).decode('utf-8', errors='replace')
                except Exception:
                    pass
            # Normaliser tous les espaces insécables en espaces classiques
            body_text = body_text.replace('\u00a0', ' ').replace('\u202f', ' ')
            return body_text.strip()

        body_html = msg_dict.get('body') or ''
        if body_html:
            clean = re.sub(r'<[^>]+>', ' ', body_html)
            clean = (clean
                     .replace('&amp;', '&')
                     .replace('&lt;', '<')
                     .replace('&gt;', '>')
                     .replace('&nbsp;', ' ')
                     .replace('&#160;', ' ')
                     .replace('&#8239;', ' '))
            # Normaliser les espaces Unicode insécables
            clean = clean.replace('\u00a0', ' ').replace('\u202f', ' ')
            clean = re.sub(r'[ \t]+', ' ', clean)
            clean = re.sub(r'\n{3,}', '\n\n', clean)
            return clean.strip()
        return ''

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _clean_amount(self, raw):
        """Convertit une chaîne de montant en float."""
        cleaned = re.sub(r'[\s\u00a0\u202f]', '', raw)
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            raise UserError(
                _("Impossible de convertir le montant '%s' en nombre.") % raw
            )

    def _parse_email_body(self, body_text):
        """Extrait les données structurées du corps de l'email."""
        self.ensure_one()

        def _extract(pattern, label):
            match = re.search(pattern, body_text, re.IGNORECASE | re.DOTALL)
            if not match:
                raise UserError(
                    _("Pattern '%s' introuvable dans le corps de l'email "
                      "(règle '%s').") % (pattern, self.name)
                )
            return match.group(1).strip()

        invoice_number = _extract(self.regex_invoice_number, 'n° facture')
        date_str = _extract(self.regex_invoice_date, 'date')
        amount_raw = _extract(self.regex_amount, 'montant')
        contract_number = _extract(self.regex_contract, 'n° contrat')

        try:
            invoice_date = datetime.strptime(date_str, '%d/%m/%Y').date()
        except ValueError:
            raise UserError(
                _("Format de date inattendu : '%s' (attendu JJ/MM/AAAA).")
                % date_str
            )

        return {
            'invoice_number': invoice_number,
            'invoice_date': invoice_date,
            'amount': self._clean_amount(amount_raw),
            'contract_number': contract_number,
        }

    # ── Produit / analytique ─────────────────────────────────────────────────

    def _find_product_by_contract(self, contract_number):
        self.ensure_one()
        attr_values = self.env['product.attribute.value'].search([
            ('attribute_id.name', '=', self.product_attribute_name),
            ('name', '=', contract_number),
        ])
        if not attr_values:
            raise UserError(
                _("Aucun produit avec l'attribut '%s' = '%s'.")
                % (self.product_attribute_name, contract_number)
            )
        ptav = self.env['product.template.attribute.value'].search([
            ('product_attribute_value_id', 'in', attr_values.ids),
        ], limit=1)
        if not ptav:
            raise UserError(
                _("Attribut '%s' = '%s' non lié à un modèle produit.")
                % (self.product_attribute_name, contract_number)
            )
        return ptav.product_tmpl_id

    def _get_analytic_distribution(self, product_tmpl):
        self.ensure_one()
        domain = [('name', 'ilike', product_tmpl.name)]
        if self.analytic_plan_id:
            domain.append(('plan_id', '=', self.analytic_plan_id.id))
        analytic_account = self.env['account.analytic.account'].search(
            domain, limit=1
        )
        if not analytic_account:
            _logger.warning(
                "Aucun compte analytique pour '%s'. Facture sans analytique.",
                product_tmpl.name
            )
            return {}
        return {str(analytic_account.id): 100.0}

    # ── Création de la facture ───────────────────────────────────────────────

    def create_vendor_bill(self, parsed_data):
        """
        Crée la facture fournisseur.
        Retourne (move, created) — created=False si doublon.
        """
        self.ensure_one()
        Move = self.env['account.move']

        existing = Move.search([
            ('ref', '=', parsed_data['invoice_number']),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)
        if existing:
            return existing, False

        product_tmpl = self._find_product_by_contract(
            parsed_data['contract_number']
        )
        analytic_distribution = self._get_analytic_distribution(product_tmpl)

        currency = self.env['res.currency'].search(
            [('name', '=', self.currency_code)], limit=1
        )
        if not currency:
            raise UserError(
                _("Devise '%s' introuvable.") % self.currency_code
            )

        journal = self.journal_id or self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            raise UserError(_("Aucun journal d'achat trouvé."))

        move = Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': parsed_data['invoice_date'],
            'ref': parsed_data['invoice_number'],
            'journal_id': journal.id,
            'currency_id': currency.id,
            'narration': _(
                "Importé automatiquement — Contrat %s — Règle '%s'"
            ) % (parsed_data['contract_number'], self.name),
            'invoice_line_ids': [(0, 0, {
                'name': '%s — %s' % (
                    product_tmpl.name, parsed_data['invoice_number']
                ),
                'account_id': self.account_id.id,
                'quantity': 1.0,
                'price_unit': parsed_data['amount'],
                'analytic_distribution': analytic_distribution or False,
            })],
        })
        _logger.info(
            "Facture créée : %s — '%s' — %.0f %s",
            move.name, product_tmpl.name,
            parsed_data['amount'], self.currency_code
        )
        return move, True

    # ── Actions UI ───────────────────────────────────────────────────────────

    def action_view_bills(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'domain': [
                ('move_type', '=', 'in_invoice'),
                ('partner_id', '=', self.partner_id.id),
                ('narration', 'ilike', "Règle '%s'" % self.name),
            ],
            'view_mode': 'list,form',
            'name': _('Factures — %s') % self.name,
            'context': {'default_move_type': 'in_invoice'},
        }

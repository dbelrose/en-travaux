# -*- coding: utf-8 -*-
"""
supplier.email.rule — Règle de parsing d'email fournisseur.

Extensions v2 :
  • Exploitation de la pièce jointe PDF (si présente et activée)
  • Extraction des lignes de détail depuis le PDF
  • Validation automatique de la facture (post)
  • Enregistrement et rapprochement automatique d'un paiement
"""

import re
import logging
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .pdf_parser import extract_pdf_text, PDF_AVAILABLE

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
                    → _get_parsing_text()       (corps email ou PDF)
                        → _parse_email_body()
                            → create_vendor_bill()
                                → account.move (facture brouillon / postée)
                                    → account.payment + rapprochement (optionnel)
    """
    _name = 'supplier.email.rule'
    _description = 'Règle de parsing email fournisseur'
    _order = 'sequence, name'
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
        help="Regex sur l'adresse expéditeur pour vérifier l'origine.\n"
             "Ex : efacture@.*edt\\.engie\\.pf"
    )
    subject_pattern = fields.Char(
        string="Pattern sujet (regex, optionnel)",
    )

    # ── Regex d'extraction (corps email ou texte PDF) ─────────────────────────
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
        string='Regex montant total',
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
    )

    # ── Comptabilité ──────────────────────────────────────────────────────────
    partner_id = fields.Many2one('res.partner', string='Fournisseur', required=True)
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
    analytic_plan_id = fields.Many2one('account.analytic.plan', string='Plan analytique')

    # ── Section PDF ───────────────────────────────────────────────────────────
    use_pdf_attachment = fields.Boolean(
        string='Exploiter la pièce jointe PDF',
        default=False,
        help="Si coché et qu'un PDF est joint à l'email, le texte est extrait "
             "du PDF pour alimenter le parsing (en remplacement ou en complément "
             "du corps de l'email)."
    )
    pdf_prefer_over_body = fields.Boolean(
        string='Préférer le PDF au corps de l\'email',
        default=True,
        help="Si coché, le texte du PDF est utilisé à la place du corps de l'email. "
             "Sinon, les deux sont concaténés (corps + PDF) pour le parsing."
    )
    pdf_extract_lines = fields.Boolean(
        string='Extraire les lignes de détail du PDF',
        default=False,
        help="Si coché, la regex de ligne est appliquée sur le texte du PDF "
             "pour créer plusieurs lignes de facture au lieu d'une seule.\n"
             "Le montant total issu de regex_amount reste le montant de référence "
             "pour la déduplication et le rapprochement."
    )
    regex_pdf_line = fields.Char(
        string='Regex ligne de détail PDF',
        help="Regex Python avec deux groupes capturants :\n"
             "  groupe 1 → libellé de la ligne\n"
             "  groupe 2 → montant de la ligne\n"
             "Exemple EDT :\n"
             "  ^(.+?)\s{2,}([\d\s\u202f,\.]+)\s*(?:FCFP|XPF)\s*$\n"
             "Chaque correspondance génère une ligne de facture."
    )
    pdf_line_account_id = fields.Many2one(
        'account.account',
        string='Compte pour les lignes PDF',
        help="Compte de charge affecté aux lignes extraites du PDF. "
             "Si vide, le compte de charge principal est utilisé."
    )
    pdf_line_tax_ids = fields.Many2many(
        'account.tax',
        'supplier_rule_pdf_line_tax_rel',
        'rule_id', 'tax_id',
        string='Taxes sur les lignes PDF',
        domain=[('type_tax_use', '=', 'purchase')],
        help="Taxes à appliquer sur les lignes de détail extraites du PDF. "
             "Laisser vide si le montant PDF est TTC."
    )

    # ── Section Paiement ─────────────────────────────────────────────────────
    auto_post_bill = fields.Boolean(
        string='Valider automatiquement la facture',
        default=False,
        help="Si coché, la facture passe de Brouillon à Validé immédiatement "
             "après sa création. Prérequis pour l'enregistrement automatique "
             "du paiement."
    )
    auto_register_payment = fields.Boolean(
        string='Enregistrer le paiement automatiquement',
        default=False,
        help="Crée un paiement sortant et le rapproche de la facture. "
             "Nécessite 'Valider automatiquement la facture'."
    )
    payment_journal_id = fields.Many2one(
        'account.journal',
        string='Journal de paiement',
        domain=[('type', 'in', ['bank', 'cash'])],
        help="Journal bancaire ou caisse utilisé pour le paiement automatique."
    )
    payment_date_source = fields.Selection([
        ('invoice_date', 'Date de la facture'),
        ('today', "Date du jour (import)"),
    ], string='Date du paiement', default='invoice_date',
        help="Source de la date utilisée pour le paiement automatique."
    )
    payment_memo = fields.Char(
        string='Mémo paiement',
        help="Libellé du paiement. Supporte les variables : "
             "{invoice_number}, {contract_number}, {partner}.\n"
             "Ex : Règlement EDT {invoice_number}"
    )

    # ── Statistiques de suivi ─────────────────────────────────────────────────
    bill_count = fields.Integer(string='Factures créées', compute='_compute_bill_count')
    last_import_date = fields.Datetime(string='Dernier import', readonly=True)
    last_import_result = fields.Char(string='Résultat dernier import', readonly=True)

    def _compute_bill_count(self):
        for rule in self:
            rule.bill_count = self.env['account.move'].search_count([
                ('move_type', '=', 'in_invoice'),
                ('partner_id', '=', rule.partner_id.id),
                ('narration', 'ilike', "Règle '%s'" % rule.name),
            ])

    # ── Contraintes ──────────────────────────────────────────────────────────

    @api.constrains('auto_register_payment', 'auto_post_bill')
    def _check_payment_requires_post(self):
        for rule in self:
            if rule.auto_register_payment and not rule.auto_post_bill:
                raise UserError(_(
                    "La règle '%s' : l'enregistrement automatique du paiement "
                    "nécessite que 'Valider automatiquement la facture' soit activé."
                ) % rule.name)

    @api.constrains('auto_register_payment', 'payment_journal_id')
    def _check_payment_journal(self):
        for rule in self:
            if rule.auto_register_payment and not rule.payment_journal_id:
                raise UserError(_(
                    "La règle '%s' : veuillez sélectionner un journal de paiement."
                ) % rule.name)

    @api.constrains('pdf_extract_lines', 'regex_pdf_line')
    def _check_pdf_lines_regex(self):
        for rule in self:
            if rule.pdf_extract_lines and not rule.regex_pdf_line:
                raise UserError(_(
                    "La règle '%s' : la regex de ligne PDF est obligatoire "
                    "lorsque 'Extraire les lignes de détail du PDF' est activé."
                ) % rule.name)

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
        """
        Appelé automatiquement par Odoo (mail.thread) lorsqu'un email
        arrive sur l'alias de cette règle via fetchmail.
        """
        custom_values = custom_values or {}
        rule_id = custom_values.get('rule_id')

        if rule_id:
            rule = self.browse(rule_id)
        else:
            rule = self._detect_rule_from_sender(msg_dict.get('email_from', ''))

        if not rule:
            _logger.warning(
                "message_new: aucune règle pour '%s'. Ignoré.",
                msg_dict.get('email_from', '?')
            )
            return super().message_new(msg_dict, custom_values)

        # Vérification expéditeur
        if rule.sender_email_pattern:
            sender = msg_dict.get('email_from', '')
            if not re.search(rule.sender_email_pattern, sender, re.IGNORECASE):
                _logger.warning(
                    "message_new: expéditeur '%s' refusé par '%s'.", sender, rule.name
                )
                rule._set_last_import_result(
                    False, "⛔ Email refusé — expéditeur '%s' non autorisé." % sender
                )
                return super().message_new(msg_dict, custom_values)

        # Extraction des pièces jointes PDF
        pdf_bytes_list = rule._extract_pdf_attachments_from_msg_dict(msg_dict)

        # Texte de parsing (corps email et/ou PDF)
        parsing_text, pdf_text = rule._get_parsing_text(msg_dict, pdf_bytes_list)

        if not parsing_text:
            _logger.error("message_new: texte de parsing vide (sujet: '%s').",
                          msg_dict.get('subject', '?'))
            rule._set_last_import_result(False, "❌ Corps de l'email vide ou illisible.")
            return super().message_new(msg_dict, custom_values)

        # Parsing principal
        try:
            parsed = rule._parse_email_body(parsing_text)
        except UserError as e:
            _logger.error("message_new: erreur parsing — %s", e)
            rule._set_last_import_result(False, "❌ " + str(e))
            return super().message_new(msg_dict, custom_values)

        # Extraction des lignes de détail PDF
        pdf_lines = []
        if rule.use_pdf_attachment and rule.pdf_extract_lines and pdf_text:
            try:
                pdf_lines = rule._parse_pdf_lines(pdf_text)
            except UserError as e:
                _logger.warning("message_new: lignes PDF — %s", e)
                # Non bloquant : on crée quand même la facture sans lignes détail

        # Création de la facture
        try:
            move, created = rule.create_vendor_bill(parsed, pdf_lines=pdf_lines)
            if created:
                status = (
                    "✔ Facture %s créée — Contrat %s — %.0f %s"
                    % (parsed['invoice_number'], parsed['contract_number'],
                       parsed['amount'], rule.currency_code)
                )
                if rule.auto_post_bill:
                    status += " [validée]"
                if rule.auto_register_payment:
                    status += " [payée & rapprochée]"
            else:
                status = "⚠ Doublon ignoré : facture %s déjà présente." % parsed['invoice_number']
            rule._set_last_import_result(created, status)
        except UserError as e:
            _logger.error("message_new: erreur création facture — %s", e)
            rule._set_last_import_result(False, "❌ " + str(e))

        return super().message_new(msg_dict, custom_values)

    # ── Gestion du texte de parsing ──────────────────────────────────────────

    def _get_parsing_text(self, msg_dict, pdf_bytes_list):
        """
        Détermine le texte à utiliser pour le parsing selon la configuration.

        Returns:
            (parsing_text: str, pdf_text: str)
            pdf_text est retourné séparément pour l'extraction de lignes.
        """
        self.ensure_one()
        body_text = self._extract_text_from_msg_dict(msg_dict)
        pdf_text = ''

        if self.use_pdf_attachment and pdf_bytes_list:
            for pdf_bytes in pdf_bytes_list:
                try:
                    extracted = extract_pdf_text(pdf_bytes)
                    if extracted.strip():
                        pdf_text = extracted
                        break  # On utilise le premier PDF lisible
                except Exception as exc:
                    _logger.warning("_get_parsing_text: erreur PDF — %s", exc)

        if not self.use_pdf_attachment or not pdf_text:
            return body_text, pdf_text

        if self.pdf_prefer_over_body:
            parsing_text = pdf_text
        else:
            parsing_text = (body_text + '\n\n' + pdf_text).strip()

        return parsing_text, pdf_text

    @staticmethod
    def _extract_pdf_attachments_from_msg_dict(msg_dict):
        """
        Extrait les bytes des pièces jointes PDF depuis msg_dict.

        msg_dict['attachments'] peut être :
          - une liste de (filename, content, mimetype, ...)  tuples
          - une liste d'objets avec attributs
        Retourne une liste de bytes (PDF bruts).
        """
        pdf_list = []
        attachments = msg_dict.get('attachments') or []
        for att in attachments:
            # Tuple (name, content, ...)
            if isinstance(att, (list, tuple)) and len(att) >= 2:
                name = att[0] or ''
                content = att[1]
                mime = att[2] if len(att) > 2 else ''
            elif hasattr(att, 'fname'):
                name = att.fname or ''
                content = att.payload
                mime = getattr(att, 'mimetype', '')
            else:
                continue

            is_pdf = (
                (isinstance(mime, str) and 'pdf' in mime.lower())
                or (isinstance(name, str) and name.lower().endswith('.pdf'))
            )
            if is_pdf and isinstance(content, bytes) and content:
                pdf_list.append(content)
        return pdf_list

    def _set_last_import_result(self, success, message):
        self.ensure_one()
        self.sudo().write({
            'last_import_date': fields.Datetime.now(),
            'last_import_result': message,
        })
        _logger.info("[%s] %s", self.name, message)

    @api.model
    def _detect_rule_from_sender(self, sender_email):
        for rule in self.search([('active', '=', True)]):
            if rule.sender_email_pattern and re.search(
                rule.sender_email_pattern, sender_email, re.IGNORECASE
            ):
                return rule
        return None

    @staticmethod
    def _extract_text_from_msg_dict(msg_dict):
        """Extrait le meilleur corps texte depuis le dict message Odoo."""
        import quopri

        body_text = msg_dict.get('body_text') or ''
        if body_text.strip():
            if '=E2=' in body_text or '=C3=' in body_text or '=AF' in body_text:
                try:
                    body_text = quopri.decodestring(
                        body_text.encode('latin-1')
                    ).decode('utf-8', errors='replace')
                except Exception:
                    pass
            body_text = body_text.replace('\u00a0', ' ').replace('\u202f', ' ')
            return body_text.strip()

        body_html = msg_dict.get('body') or ''
        if body_html:
            clean = re.sub(r'<[^>]+>', ' ', body_html)
            clean = (clean
                     .replace('&amp;', '&').replace('&lt;', '<')
                     .replace('&gt;', '>').replace('&nbsp;', ' ')
                     .replace('&#160;', ' ').replace('&#8239;', ' '))
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
        """Extrait les données structurées du texte (corps email ou PDF)."""
        self.ensure_one()

        def _extract(pattern, label):
            match = re.search(pattern, body_text, re.IGNORECASE | re.DOTALL)
            if not match:
                raise UserError(
                    _("Pattern '%s' introuvable (règle '%s').") % (pattern, self.name)
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
                _("Format de date inattendu : '%s' (attendu JJ/MM/AAAA).") % date_str
            )

        return {
            'invoice_number': invoice_number,
            'invoice_date': invoice_date,
            'amount': self._clean_amount(amount_raw),
            'contract_number': contract_number,
        }

    def _parse_pdf_lines(self, pdf_text):
        """
        Extrait les lignes de détail depuis le texte PDF selon regex_pdf_line.

        La regex doit avoir exactement 2 groupes capturants :
          groupe 1 → libellé de la ligne
          groupe 2 → montant

        Returns:
            list of dict : [{'name': str, 'amount': float}, ...]
        """
        self.ensure_one()
        if not self.regex_pdf_line:
            return []

        pattern = self.regex_pdf_line
        lines = []
        try:
            for match in re.finditer(pattern, pdf_text, re.IGNORECASE | re.MULTILINE):
                if len(match.groups()) < 2:
                    _logger.warning(
                        "_parse_pdf_lines: la regex doit avoir 2 groupes (règle '%s').",
                        self.name
                    )
                    break
                label = match.group(1).strip()
                amount_raw = match.group(2).strip()
                try:
                    amount = self._clean_amount(amount_raw)
                except UserError:
                    _logger.warning(
                        "_parse_pdf_lines: montant illisible '%s' — ligne ignorée.",
                        amount_raw
                    )
                    continue
                if label and amount != 0.0:
                    lines.append({'name': label, 'amount': amount})
        except re.error as exc:
            raise UserError(
                _("Regex de ligne PDF invalide (règle '%s') : %s") % (self.name, exc)
            )

        _logger.info(
            "_parse_pdf_lines [%s] : %d ligne(s) extraite(s) du PDF.",
            self.name, len(lines)
        )
        return lines

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
        analytic_account = self.env['account.analytic.account'].search(domain, limit=1)
        if not analytic_account:
            _logger.warning(
                "Aucun compte analytique pour '%s'. Facture sans analytique.",
                product_tmpl.name
            )
            return {}
        return {str(analytic_account.id): 100.0}

    # ── Création de la facture ───────────────────────────────────────────────

    def create_vendor_bill(self, parsed_data, pdf_lines=None):
        """
        Crée la facture fournisseur, l'auto-valide et enregistre le paiement
        selon la configuration de la règle.

        Args:
            parsed_data (dict) : résultat de _parse_email_body()
            pdf_lines   (list) : lignes de détail issues de _parse_pdf_lines()
                                  Si vide/None → une seule ligne avec le montant total.

        Returns:
            (account.move, bool created)
        """
        self.ensure_one()
        pdf_lines = pdf_lines or []
        Move = self.env['account.move']

        # Déduplication
        existing = Move.search([
            ('ref', '=', parsed_data['invoice_number']),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)
        if existing:
            return existing, False

        # Résolution du produit et de l'analytique
        product_tmpl = self._find_product_by_contract(parsed_data['contract_number'])
        analytic_distribution = self._get_analytic_distribution(product_tmpl)

        # Devise
        currency = self.env['res.currency'].search(
            [('name', '=', self.currency_code)], limit=1
        )
        if not currency:
            raise UserError(_("Devise '%s' introuvable.") % self.currency_code)

        # Journal
        journal = self.journal_id or self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            raise UserError(_("Aucun journal d'achat trouvé."))

        # Construction des lignes de facture
        invoice_line_ids = self._build_invoice_lines(
            parsed_data, product_tmpl, analytic_distribution, pdf_lines
        )

        # Création
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
            'invoice_line_ids': invoice_line_ids,
        })

        _logger.info(
            "Facture créée : %s — '%s' — %.0f %s (%d ligne(s))",
            move.name, product_tmpl.name,
            parsed_data['amount'], self.currency_code, len(invoice_line_ids)
        )

        # Validation automatique
        if self.auto_post_bill:
            move.action_post()
            _logger.info("Facture %s validée automatiquement.", move.name)

            # Paiement et rapprochement automatiques
            if self.auto_register_payment:
                self._register_and_reconcile_payment(move, parsed_data)

        return move, True

    def _build_invoice_lines(self, parsed_data, product_tmpl,
                             analytic_distribution, pdf_lines):
        """
        Construit les commandes ORM pour invoice_line_ids.

        Si pdf_lines est fourni et non vide → une ligne par entrée PDF.
        Sinon → une seule ligne avec le montant total parsé.
        """
        self.ensure_one()
        invoice_number = parsed_data['invoice_number']

        if pdf_lines:
            line_account = self.pdf_line_account_id or self.account_id
            tax_ids = [(6, 0, self.pdf_line_tax_ids.ids)] if self.pdf_line_tax_ids else []
            lines = []
            for pdf_line in pdf_lines:
                vals = {
                    'name': '%s — %s' % (pdf_line['name'], invoice_number),
                    'account_id': line_account.id,
                    'quantity': 1.0,
                    'price_unit': pdf_line['amount'],
                    'analytic_distribution': analytic_distribution or False,
                }
                if tax_ids:
                    vals['tax_ids'] = tax_ids
                lines.append((0, 0, vals))
            return lines

        # Ligne unique
        return [(0, 0, {
            'name': '%s — %s' % (product_tmpl.name, invoice_number),
            'account_id': self.account_id.id,
            'quantity': 1.0,
            'price_unit': parsed_data['amount'],
            'analytic_distribution': analytic_distribution or False,
        })]

    # ── Paiement et rapprochement ─────────────────────────────────────────────

    def _register_and_reconcile_payment(self, move, parsed_data):
        """
        Crée un paiement fournisseur sortant et le rapproche de la facture.

        Le paiement est créé en brouillon puis validé (action_post).
        Le rapprochement est ensuite effectué sur les lignes de compte
        de type 'liability_payable'.

        Args:
            move        (account.move) : facture validée
            parsed_data (dict)         : données parsées (invoice_date, amount…)
        """
        self.ensure_one()
        if not self.payment_journal_id:
            raise UserError(
                _("Règle '%s' : journal de paiement non configuré.") % self.name
            )
        if move.state != 'posted':
            raise UserError(
                _("Règle '%s' : impossible de payer la facture '%s' "
                  "(elle n'est pas validée).") % (self.name, move.name)
            )

        # Date du paiement
        payment_date = (
            parsed_data['invoice_date']
            if self.payment_date_source == 'invoice_date'
            else date.today()
        )

        # Mémo
        memo_template = self.payment_memo or 'Règlement {invoice_number}'
        memo = memo_template.format(
            invoice_number=parsed_data.get('invoice_number', ''),
            contract_number=parsed_data.get('contract_number', ''),
            partner=self.partner_id.name or '',
        )

        # Montant réel de la facture (peut différer du montant parsé
        # si des taxes ont été appliquées sur les lignes PDF)
        amount_to_pay = move.amount_residual

        Payment = self.env['account.payment']
        payment = Payment.create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'journal_id': self.payment_journal_id.id,
            'currency_id': move.currency_id.id,
            'amount': amount_to_pay,
            'date': payment_date,
            'ref': memo,
        })
        payment.action_post()

        _logger.info(
            "Paiement créé : %s — %.0f %s — %s",
            payment.name, amount_to_pay, self.currency_code, payment_date
        )

        # Rapprochement : lignes payables de la facture ↔ lignes du paiement
        self._reconcile_move_and_payment(move, payment)

    def _reconcile_move_and_payment(self, move, payment):
        """
        Rapproche les lignes 'liability_payable' de la facture et du paiement.
        """
        payable_types = ('liability_payable',)

        invoice_lines = move.line_ids.filtered(
            lambda l: l.account_id.account_type in payable_types
            and not l.reconciled
        )
        payment_lines = payment.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in payable_types
            and not l.reconciled
        )

        to_reconcile = invoice_lines | payment_lines
        if len(to_reconcile) < 2:
            _logger.warning(
                "_reconcile: pas assez de lignes réconciliables pour %s / %s",
                move.name, payment.name
            )
            return

        try:
            to_reconcile.reconcile()
            _logger.info(
                "Rapprochement effectué : facture %s ↔ paiement %s",
                move.name, payment.name
            )
        except Exception as exc:
            _logger.error(
                "_reconcile: erreur rapprochement %s / %s — %s",
                move.name, payment.name, exc
            )
            raise UserError(
                _("Erreur lors du rapprochement de %s avec %s : %s")
                % (move.name, payment.name, exc)
            )

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

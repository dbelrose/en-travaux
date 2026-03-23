# -*- coding: utf-8 -*-
"""
supplier.email.rule — Règle de parsing d'email fournisseur.

Extensions v2 :
  • Exploitation de la pièce jointe PDF (si présente et activée)
  • Extraction des lignes de détail depuis le PDF
  • Validation automatique de la facture (post)
  • Enregistrement et rapprochement automatique d'un paiement

Extensions v3 :
  • Support des Tantièmes via le champ optionnel tantieme_attribute_id.
    Séparation des rôles :
      - product_attribute_id → identifie le(s) produit(s) (ex: 'N° de lot')
      - tantieme_attribute_id → lit la quote-part sur chaque produit
                                   (ex: 'Tantièmes' → '450/10000')
    En mode tantième, plusieurs lots peuvent correspondre au même n° de contrat :
    une facture est alors créée par produit/lot pour la comptabilité analytique.
    Le montant de chaque facture = tantième_lot × montant_total_email.
    Déduplication : (invoice_number + '#' + product_name, partner) en mode tantième.
    Si tantieme_attribute_id est vide → comportement mono-produit inchangé.

Extensions v3.1 :
  • product_attribute_id et tantieme_attribute_id passent de Char à Many2one
    vers product.attribute — sélection depuis une liste plutôt que saisie libre.
    Des propriétés de compatibilité exposent encore .product_attribute_name
    et .tantieme_attribute_name pour le code interne.

Extensions v3.2 :
  • _extract_facturx_xml utilise désormais le module Python factur-x
    (pip install factur-x) en priorité.
    Avantages :
      - Gère tous les profils EN 16931 / ZUGFeRD / Factur-X automatiquement
      - Détecte le flavor (MINIMUM, EN 16931, EXTENDED…) et le logue
      - Ne dépend plus d'une liste figée de noms de fichiers XML
    Fallback transparent vers pypdf si factur-x n'est pas installé.
"""

import re
import logging
from datetime import datetime, date

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from .pdf_parser import extract_pdf_text, PDF_AVAILABLE

_logger = logging.getLogger(__name__)

# ── Détection du module factur-x au chargement ────────────────────────────────
_FACTURX_OK = False
try:
    from facturx import get_facturx_xml_from_pdf  # noqa: F401
    _FACTURX_OK = True
    _logger.info(
        "supplier_email_rule: module factur-x disponible — extraction XML optimisée."
    )
except ImportError:
    _logger.info(
        "supplier_email_rule: module factur-x absent — fallback pypdf pour "
        "l'extraction XML.\nPour une meilleure compatibilité : pip install factur-x"
    )


class SupplierEmailRule(models.Model):
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
        help="Obligatoire si Factur-X non activé.\n"
             "Ex : facture\\s+(\\S+)\\s+du"
    )
    regex_invoice_date = fields.Char(
        string='Regex date (JJ/MM/AAAA)',
        help="Obligatoire si Factur-X non activé.\n"
             "Ex : du\\s+(\\d{2}/\\d{2}/\\d{4})"
    )
    regex_amount = fields.Char(
        string='Regex montant total',
        help="Obligatoire si Factur-X non activé.\n"
             "Ex : montant de ([\\d\\s\\u00a0\\u202f,\\.]+?)\\s*(?:FCFP|EUR|XPF)"
    )
    regex_contract = fields.Char(
        string='Regex n° contrat',
        help="Obligatoire si Factur-X non activé.\n"
             "Recommandé même en mode Factur-X : utilisé en fallback si le "
             "champ contrat est absent du XML.\n"
             "Ex : contrat\\s+([\\w\\-]+)"
    )
    currency_code = fields.Char(
        string='Code devise',
        default='XPF',
    )

    # ── Lien produit / analytique ─────────────────────────────────────────────
    product_attribute_id = fields.Many2one(
        'product.attribute',
        string='Attribut produit',
        required=True,
        help="Attribut produit utilisé pour retrouver le produit "
             "à partir du n° de contrat extrait de l'email.\n"
             "Ex : 'N° de contrat EDT', 'N° de lot', 'Référence client'"
    )
    tantieme_attribute_id = fields.Many2one(
        'product.attribute',
        string='Attribut tantième',
        help="Si renseigné, le module cherche cet attribut sur le produit "
             "identifié par 'Attribut produit' et interprète sa valeur "
             "comme une fraction représentant la quote-part à facturer.\n\n"
             "Ex : 'Tantièmes'\n\n"
             "Formes acceptées pour la valeur de l'attribut :\n"
             "  • Fraction entière : 450/10000\n"
             "  • Décimal virgule  : 0,045\n"
             "  • Décimal point    : 0.045\n\n"
             "Si l'attribut est absent sur le produit → facteur = 1,0 "
             "(montant intégral, non bloquant).\n"
             "Si ce champ est vide → comportement normal (facteur = 1,0)."
    )

    # Propriétés de compatibilité — utilisées dans les logs et messages d'erreur
    @property
    def product_attribute_name(self):
        return self.product_attribute_id.name if self.product_attribute_id else ''

    @property
    def tantieme_attribute_name(self):
        return self.tantieme_attribute_id.name if self.tantieme_attribute_id else ''

    # ── Factur-X (XML embarqué dans les PDFs Odoo) ────────────────────────────
    facturx_contract_field = fields.Selection([
        ('contract_ref',  'ContractReferencedDocument — référence du contrat'),
        ('buyer_ref',     'BuyerReference — référence acheteur'),
        ('seller_order',  'SellerOrderReferencedDocument — commande vendeur'),
        ('buyer_order',   'BuyerOrderReferencedDocument — commande acheteur'),
    ],
        string='Champ n° contrat dans le XML Factur-X',
        default='contract_ref',
        help="Lorsque le PDF joint contient un XML Factur-X (factures émises "
             "depuis Odoo ou tout logiciel compatible EN 16931), ce champ "
             "indique quel élément XML utiliser comme n° de contrat.\n\n"
             "• ContractReferencedDocument → champ 'Référence du contrat' "
             "  (BT-12 EN16931) — à renseigner côté fournisseur Odoo.\n"
             "• BuyerReference → référence acheteur libre (BT-10).\n"
             "• Les données Factur-X (n° facture, date, montant, lignes) "
             "  sont utilisées en priorité sur les regex email/PDF.\n\n"
             "Laisser vide (non sélectionné) pour désactiver le parsing "
             "Factur-X sur cette règle."
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
        string="Préférer le PDF au corps de l'email",
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
             r"Exemple EDT : ^(.+?)\s{2,}([\d\s\u202f,\.]+)\s*(?:FCFP|XPF)\s*$"
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

    @api.constrains(
        'facturx_contract_field',
        'regex_invoice_number', 'regex_invoice_date',
        'regex_amount', 'regex_contract',
    )
    def _check_regex_or_facturx(self):
        for rule in self:
            if rule.facturx_contract_field:
                if not rule.regex_contract:
                    _logger.warning(
                        "Règle '%s' (Factur-X) : regex_contract vide — "
                        "si le champ contrat est absent du XML, la facture "
                        "sera rejetée faute de n° de contrat.",
                        rule.name,
                    )
            else:
                missing = [
                    label for field, label in [
                        ('regex_invoice_number', 'Regex n° facture'),
                        ('regex_invoice_date',   'Regex date'),
                        ('regex_amount',         'Regex montant total'),
                        ('regex_contract',       'Regex n° contrat'),
                    ] if not getattr(rule, field)
                ]
                if missing:
                    raise UserError(_(
                        "La règle '%s' : les champs suivants sont obligatoires "
                        "lorsque Factur-X n'est pas activé :\n• %s"
                    ) % (rule.name, '\n• '.join(missing)))

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

        pdf_bytes_list = rule._extract_pdf_attachments_from_msg_dict(msg_dict)

        facturx_parsed = None
        facturx_lines = []
        if rule.facturx_contract_field and pdf_bytes_list:
            for pdf_bytes in pdf_bytes_list:
                xml_bytes = rule._extract_facturx_xml(pdf_bytes)
                if xml_bytes:
                    facturx_parsed, facturx_lines = rule._parse_facturx_data(xml_bytes)
                    if facturx_parsed:
                        _logger.info(
                            "message_new [%s] : données Factur-X utilisées "
                            "(facture %s).",
                            rule.name, facturx_parsed.get('invoice_number', '?'),
                        )
                    break

        parsing_text, pdf_text = rule._get_parsing_text(msg_dict, pdf_bytes_list)

        if not parsing_text and not facturx_parsed:
            _logger.error("message_new: texte de parsing vide (sujet: '%s').",
                          msg_dict.get('subject', '?'))
            rule._set_last_import_result(False, "❌ Corps de l'email vide ou illisible.")
            return super().message_new(msg_dict, custom_values)

        try:
            if facturx_parsed:
                parsed = facturx_parsed
                if not parsed.get('contract_number') and parsing_text:
                    try:
                        regex_data = rule._parse_email_body(parsing_text)
                        parsed['contract_number'] = regex_data['contract_number']
                        _logger.info(
                            "message_new [%s] : n° contrat '%s' récupéré "
                            "par regex (Factur-X ne le contenait pas).",
                            rule.name, parsed['contract_number'],
                        )
                    except UserError as e:
                        _logger.warning(
                            "message_new [%s] : n° contrat introuvable par "
                            "regex — %s", rule.name, e,
                        )
                        rule._set_last_import_result(
                            False,
                            "❌ N° de contrat introuvable (Factur-X + regex) : %s" % e
                        )
                        return super().message_new(msg_dict, custom_values)
            else:
                parsed = rule._parse_email_body(parsing_text)
        except UserError as e:
            _logger.error("message_new: erreur parsing — %s", e)
            rule._set_last_import_result(False, "❌ " + str(e))
            return super().message_new(msg_dict, custom_values)

        if facturx_lines:
            pdf_lines = facturx_lines
            _logger.info(
                "message_new [%s] : %d ligne(s) issues du XML Factur-X.",
                rule.name, len(pdf_lines),
            )
        else:
            pdf_lines = []
            if rule.use_pdf_attachment and rule.pdf_extract_lines and pdf_text:
                try:
                    pdf_lines = rule._parse_pdf_lines(pdf_text)
                except UserError as e:
                    _logger.warning("message_new: lignes PDF — %s", e)

        try:
            results = rule.create_vendor_bills(parsed, pdf_lines=pdf_lines)
            nb_created = sum(1 for _, created in results if created)
            nb_skipped = len(results) - nb_created

            if nb_created == 0:
                status = "⚠ Doublon ignoré : facture %s déjà présente." % parsed['invoice_number']
            else:
                status = (
                    "✔ %d facture(s) créée(s) — Contrat %s — Total %.0f %s"
                    % (nb_created, parsed['contract_number'],
                       parsed['amount'], rule.currency_code)
                )
                if nb_skipped:
                    status += " (%d doublon(s) ignoré(s))" % nb_skipped
                if rule.auto_post_bill:
                    status += " [validée(s)]"
                if rule.auto_register_payment:
                    status += " [payée(s) & rapprochée(s)]"

            rule._set_last_import_result(nb_created > 0, status)
        except UserError as e:
            _logger.error("message_new: erreur création facture — %s", e)
            rule._set_last_import_result(False, "❌ " + str(e))

        return super().message_new(msg_dict, custom_values)

    # ── Gestion du texte de parsing ──────────────────────────────────────────

    def _get_parsing_text(self, msg_dict, pdf_bytes_list):
        self.ensure_one()
        body_text = self._extract_text_from_msg_dict(msg_dict)
        pdf_text = ''

        if self.use_pdf_attachment and pdf_bytes_list:
            for pdf_bytes in pdf_bytes_list:
                try:
                    extracted = extract_pdf_text(pdf_bytes)
                    if extracted.strip():
                        pdf_text = extracted
                        break
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
        pdf_list = []
        attachments = msg_dict.get('attachments') or []
        for att in attachments:
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
        cleaned = re.sub(r'[\s\u00a0\u202f]', '', raw)
        cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            raise UserError(
                _("Impossible de convertir le montant '%s' en nombre.") % raw
            )

    def _parse_email_body(self, body_text):
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
        self.ensure_one()
        if not self.regex_pdf_line:
            return []

        lines = []
        try:
            for match in re.finditer(self.regex_pdf_line, pdf_text,
                                     re.IGNORECASE | re.MULTILINE):
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

    # ── Tantièmes ─────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_tantieme_factor(raw_value):
        raw = (raw_value or '').strip()
        if not raw:
            raise UserError(_("Valeur de tantième vide."))

        fraction_match = re.match(r'^\s*(\d[\d\s]*)\s*/\s*(\d[\d\s]*)\s*$', raw)
        if fraction_match:
            numerator_str = re.sub(r'\s', '', fraction_match.group(1))
            denominator_str = re.sub(r'\s', '', fraction_match.group(2))
            try:
                numerator = int(numerator_str)
                denominator = int(denominator_str)
            except ValueError:
                raise UserError(
                    _("Tantième : impossible de lire la fraction '%s'.") % raw
                )
            if denominator == 0:
                raise UserError(
                    _("Tantième : le dénominateur ne peut pas être zéro ('%s').") % raw
                )
            factor = numerator / denominator
        else:
            decimal_str = raw.replace(',', '.').replace(' ', '')
            try:
                factor = float(decimal_str)
            except ValueError:
                raise UserError(
                    _("Tantième : impossible de convertir '%s' en nombre.") % raw
                )

        if factor <= 0:
            raise UserError(
                _("Tantième : le facteur doit être strictement positif "
                  "(valeur : '%s').") % raw
            )
        if factor > 1:
            raise UserError(
                _("Tantième : le facteur ne peut pas dépasser 1 "
                  "(valeur obtenue : %.6f depuis '%s').") % (factor, raw)
            )
        return factor

    def _get_tantieme_factor(self, product_tmpl):
        self.ensure_one()

        if not self.tantieme_attribute_id:
            return 1.0

        ptav = self.env['product.template.attribute.value'].search([
            ('product_tmpl_id', '=', product_tmpl.id),
            ('attribute_id', '=', self.tantieme_attribute_id.id),
        ], limit=1)

        if not ptav:
            _logger.warning(
                "_get_tantieme_factor [%s] : attribut '%s' introuvable sur "
                "le produit '%s' — facteur = 1.0 (montant intégral).",
                self.name, self.tantieme_attribute_id.name, product_tmpl.name
            )
            return 1.0

        raw_value = ptav.product_attribute_value_id.name
        factor = self._parse_tantieme_factor(raw_value)
        _logger.info(
            "_get_tantieme_factor [%s] : produit '%s' — %s = '%s' → %.6f",
            self.name, product_tmpl.name,
            self.tantieme_attribute_id.name, raw_value, factor
        )
        return factor

    # ── Factur-X — extraction XML ─────────────────────────────────────────────

    _FACTURX_NS = {
        'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
        'ram': ('urn:un:unece:uncefact:data:standard'
                ':ReusableAggregateBusinessInformationEntity:100'),
        'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
    }

    @staticmethod
    def _extract_facturx_xml(pdf_bytes):
        """
        Extrait le XML Factur-X / ZUGFeRD embarqué dans un PDF.

        Stratégie en deux temps :

        1. Module factur-x (pip install factur-x) — prioritaire.
           `get_facturx_xml_from_pdf` gère nativement tous les profils
           EN 16931 / ZUGFeRD 1.x-2.x / Factur-X / XRechnung sans qu'il
           soit nécessaire de connaître le nom du fichier XML embarqué.
           Lève une exception si le PDF ne contient pas de XML valide —
           ce qui est traité comme un résultat None (pas d'erreur bloquante).

        2. Fallback pypdf — utilisé si factur-x n'est pas installé.
           Cherche dans reader.attachments par nom de fichier connu,
           puis par contenu (balise CrossIndustryInvoice).

        Returns:
            bytes — contenu XML brut, ou None si absent/illisible.
        """
        import io

        # ── Chemin 1 : module factur-x ────────────────────────────────────────
        if _FACTURX_OK:
            try:
                from facturx import get_facturx_xml_from_pdf
                xml_bytes, flavor = get_facturx_xml_from_pdf(
                    io.BytesIO(pdf_bytes),
                    check_xsd=False,
                )
                if xml_bytes:
                    if isinstance(xml_bytes, str):
                        xml_bytes = xml_bytes.encode('utf-8')
                    _logger.debug(
                        "_extract_facturx_xml : XML extrait via factur-x "
                        "(flavor=%s, %d octets).",
                        flavor, len(xml_bytes),
                    )
                    return xml_bytes
            except Exception as exc:
                # PDF sans XML Factur-X valide : cas normal, pas une erreur
                _logger.debug(
                    "_extract_facturx_xml (factur-x) : pas de XML ou erreur "
                    "(%s) — fallback pypdf.", exc,
                )

        # ── Chemin 2 : fallback pypdf ─────────────────────────────────────────
        _KNOWN_NAMES = frozenset((
            'factur-x.xml', 'zugferd-invoice.xml', 'zugferd.xml',
            'facturx.xml', 'xrechnung.xml',
        ))
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            attachments = reader.attachments or {}

            # Recherche par nom de fichier connu
            for name, content_list in attachments.items():
                if name.lower() in _KNOWN_NAMES:
                    data = (content_list[0]
                            if isinstance(content_list, list)
                            else content_list)
                    if isinstance(data, bytes) and data.strip():
                        _logger.debug(
                            "_extract_facturx_xml (pypdf) : '%s' trouvé "
                            "(%d octets).", name, len(data),
                        )
                        return data

            # Recherche par contenu (noms non standards)
            for name, content_list in attachments.items():
                if name.lower().endswith('.xml'):
                    data = (content_list[0]
                            if isinstance(content_list, list)
                            else content_list)
                    if isinstance(data, bytes) and b'CrossIndustryInvoice' in data:
                        _logger.debug(
                            "_extract_facturx_xml (pypdf) : '%s' détecté "
                            "par contenu.", name,
                        )
                        return data

        except ImportError:
            _logger.debug("_extract_facturx_xml : pypdf non disponible.")
        except Exception as exc:
            _logger.debug("_extract_facturx_xml (pypdf) : erreur — %s", exc)

        return None

    # ── Factur-X — parsing des données ───────────────────────────────────────

    def _parse_facturx_data(self, xml_bytes):
        """
        Parse le XML Factur-X et retourne (parsed_dict, pdf_lines).

        Extrait via ElementTree :
          n° facture, date, montant TTC, n° de contrat (selon
          facturx_contract_field), et les lignes de détail.
        """
        self.ensure_one()
        import xml.etree.ElementTree as ET

        CONTRACT_XPATHS = {
            'contract_ref': (
                './/ram:ApplicableHeaderTradeAgreement'
                '/ram:ContractReferencedDocument/ram:IssuerAssignedID'
            ),
            'buyer_ref': (
                './/ram:ApplicableHeaderTradeAgreement/ram:BuyerReference'
            ),
            'seller_order': (
                './/ram:ApplicableHeaderTradeAgreement'
                '/ram:SellerOrderReferencedDocument/ram:IssuerAssignedID'
            ),
            'buyer_order': (
                './/ram:ApplicableHeaderTradeAgreement'
                '/ram:BuyerOrderReferencedDocument/ram:IssuerAssignedID'
            ),
        }

        ns = self._FACTURX_NS

        def _find(root, xpath):
            el = root.find(xpath, ns)
            return (el.text or '').strip() if el is not None else ''

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            _logger.warning("_parse_facturx_data : XML invalide — %s", exc)
            return None, []

        # N° de facture
        invoice_number = _find(root, './/rsm:ExchangedDocument/ram:ID')
        if not invoice_number:
            _logger.warning("_parse_facturx_data : ram:ID introuvable.")
            return None, []

        # Date
        date_el = root.find(
            './/rsm:ExchangedDocument/ram:IssueDateTime/udt:DateTimeString', ns
        )
        if date_el is None or not date_el.text:
            _logger.warning("_parse_facturx_data : date introuvable.")
            return None, []

        date_raw = date_el.text.strip()
        date_fmt = date_el.get('format', '102')
        try:
            if date_fmt == '102' and len(date_raw) == 8:
                invoice_date = datetime.strptime(date_raw, '%Y%m%d').date()
            elif len(date_raw) == 10 and '-' in date_raw:
                invoice_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
            else:
                _logger.warning(
                    "_parse_facturx_data : format date inconnu '%s' (format=%s).",
                    date_raw, date_fmt,
                )
                return None, []
        except ValueError as exc:
            _logger.warning(
                "_parse_facturx_data : date illisible '%s' — %s", date_raw, exc
            )
            return None, []

        # Montant TTC
        amount_str = _find(
            root,
            './/ram:SpecifiedTradeSettlementHeaderMonetarySummation'
            '/ram:GrandTotalAmount'
        )
        if not amount_str:
            amount_str = _find(
                root,
                './/ram:SpecifiedTradeSettlementHeaderMonetarySummation'
                '/ram:TaxInclusiveTotalAmount'
            )
        if not amount_str:
            _logger.warning("_parse_facturx_data : montant TTC introuvable.")
            return None, []

        try:
            amount = float(amount_str.replace(',', '.'))
        except ValueError:
            _logger.warning(
                "_parse_facturx_data : montant illisible '%s'.", amount_str
            )
            return None, []

        # N° de contrat
        contract_number = ''
        if self.facturx_contract_field:
            xpath = CONTRACT_XPATHS.get(self.facturx_contract_field, '')
            if xpath:
                contract_number = _find(root, xpath)

        if not contract_number:
            _logger.warning(
                "_parse_facturx_data [%s] : n° de contrat introuvable "
                "(champ '%s'). Fallback regex.",
                self.name, self.facturx_contract_field or '(non configuré)',
            )

        # Lignes de détail
        pdf_lines = []
        for item in root.findall('.//ram:IncludedSupplyChainTradeLineItem', ns):
            label = _find(item, './/ram:SpecifiedTradeProduct/ram:Name')
            amount_line_str = _find(
                item,
                './/ram:SpecifiedLineTradeSettlement'
                '/ram:SpecifiedTradeSettlementLineMonetarySummation'
                '/ram:LineTotalAmount'
            )
            if label and amount_line_str:
                try:
                    line_amount = float(amount_line_str.replace(',', '.'))
                    if line_amount != 0.0:
                        pdf_lines.append({'name': label, 'amount': line_amount})
                except ValueError:
                    _logger.debug(
                        "_parse_facturx_data : montant ligne illisible '%s'.",
                        amount_line_str,
                    )

        _logger.info(
            "_parse_facturx_data [%s] : facture %s — %s — %.2f — "
            "%d ligne(s) — contrat '%s'.",
            self.name, invoice_number, invoice_date, amount,
            len(pdf_lines), contract_number or '?',
        )

        return {
            'invoice_number':  invoice_number,
            'invoice_date':    invoice_date,
            'amount':          amount,
            'contract_number': contract_number,
        }, pdf_lines

    # ── Produit / analytique ─────────────────────────────────────────────────

    def _find_product_by_contract(self, contract_number):
        self.ensure_one()
        if not self.product_attribute_id:
            raise UserError(
                _("Aucun attribut produit configuré sur la règle '%s'.") % self.name
            )

        attr_values = self.env['product.attribute.value'].search([
            ('attribute_id', '=', self.product_attribute_id.id),
            ('name', '=', contract_number),
        ])
        if not attr_values:
            raise UserError(
                _("Aucun produit avec l'attribut '%s' = '%s'.")
                % (self.product_attribute_id.name, contract_number)
            )
        ptavs = self.env['product.template.attribute.value'].search([
            ('product_attribute_value_id', 'in', attr_values.ids),
        ])
        if not ptavs:
            raise UserError(
                _("Attribut '%s' = '%s' non lié à un modèle produit.")
                % (self.product_attribute_id.name, contract_number)
            )

        product_tmpls = ptavs.mapped('product_tmpl_id')

        if not self.tantieme_attribute_id and len(product_tmpls) > 1:
            _logger.warning(
                "_find_product_by_contract [%s] : %d produits trouvés pour "
                "'%s' = '%s' sans mode tantième — premier produit utilisé : '%s'.",
                self.name, len(product_tmpls),
                self.product_attribute_id.name, contract_number,
                product_tmpls[0].name,
            )
            return product_tmpls[:1]

        _logger.info(
            "_find_product_by_contract [%s] : %d produit(s) pour '%s' = '%s'.",
            self.name, len(product_tmpls),
            self.product_attribute_id.name, contract_number,
        )
        return product_tmpls

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

    # ── Création des factures ────────────────────────────────────────────────

    def create_vendor_bills(self, parsed_data, pdf_lines=None):
        self.ensure_one()
        pdf_lines = pdf_lines or []
        product_tmpls = self._find_product_by_contract(parsed_data['contract_number'])
        results = []
        for product_tmpl in product_tmpls:
            move, created = self._create_single_vendor_bill(
                parsed_data, product_tmpl, pdf_lines=pdf_lines
            )
            results.append((move, created))
        return results

    def _create_single_vendor_bill(self, parsed_data, product_tmpl, pdf_lines=None):
        self.ensure_one()
        pdf_lines = pdf_lines or []
        Move = self.env['account.move']

        dedup_ref = (
            '%s#%s' % (parsed_data['invoice_number'], product_tmpl.name)
            if self.tantieme_attribute_id
            else parsed_data['invoice_number']
        )

        existing = Move.search([
            ('ref', '=', dedup_ref),
            ('move_type', '=', 'in_invoice'),
            ('partner_id', '=', self.partner_id.id),
        ], limit=1)
        if existing:
            _logger.info(
                "_create_single_vendor_bill [%s] — doublon ignoré : '%s'.",
                self.name, dedup_ref,
            )
            return existing, False

        analytic_distribution = self._get_analytic_distribution(product_tmpl)
        total_amount = parsed_data['amount']
        tantieme_factor = self._get_tantieme_factor(product_tmpl)
        effective_amount = round(total_amount * tantieme_factor, 2)

        if tantieme_factor != 1.0:
            _logger.info(
                "_create_single_vendor_bill [%s] '%s' — Tantième : "
                "%.0f × %.6f = %.2f %s",
                self.name, product_tmpl.name,
                total_amount, tantieme_factor, effective_amount, self.currency_code,
            )

        currency = self.env['res.currency'].search(
            [('name', '=', self.currency_code)], limit=1
        )
        if not currency:
            raise UserError(_("Devise '%s' introuvable.") % self.currency_code)

        journal = self.journal_id or self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not journal:
            raise UserError(_("Aucun journal d'achat trouvé."))

        invoice_line_ids = self._build_invoice_lines(
            parsed_data, product_tmpl, analytic_distribution,
            pdf_lines, effective_amount=effective_amount,
            tantieme_factor=tantieme_factor,
        )

        narration_extra = ''
        if tantieme_factor != 1.0:
            narration_extra = _(
                " — Tantième %.6f (total appel : %.0f %s)"
            ) % (tantieme_factor, total_amount, self.currency_code)

        move = Move.create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': parsed_data['invoice_date'],
            'ref': dedup_ref,
            'journal_id': journal.id,
            'currency_id': currency.id,
            'narration': _(
                "Importé automatiquement — Contrat %s — Règle '%s'%s"
            ) % (parsed_data['contract_number'], self.name, narration_extra),
            'invoice_line_ids': invoice_line_ids,
        })

        _logger.info(
            "Facture créée : %s — '%s' — %.2f %s (%d ligne(s))%s",
            move.name, product_tmpl.name,
            effective_amount, self.currency_code, len(invoice_line_ids),
            (" [tantième %.6f]" % tantieme_factor) if tantieme_factor != 1.0 else '',
        )

        if self.auto_post_bill:
            move.action_post()
            _logger.info("Facture %s validée automatiquement.", move.name)
            if self.auto_register_payment:
                self._register_and_reconcile_payment(move, parsed_data)

        return move, True

    def _build_invoice_lines(self, parsed_data, product_tmpl,
                             analytic_distribution, pdf_lines,
                             effective_amount=None, tantieme_factor=None):
        self.ensure_one()
        invoice_number = parsed_data['invoice_number']

        if effective_amount is None:
            effective_amount = parsed_data['amount']

        if pdf_lines:
            line_account = self.pdf_line_account_id or self.account_id
            tax_ids = [(6, 0, self.pdf_line_tax_ids.ids)] if self.pdf_line_tax_ids else []
            lines = []
            for pdf_line in pdf_lines:
                line_amount = (
                    round(pdf_line['amount'] * tantieme_factor, 2)
                    if tantieme_factor is not None
                    else pdf_line['amount']
                )
                vals = {
                    'name': '%s — %s' % (pdf_line['name'], invoice_number),
                    'account_id': line_account.id,
                    'quantity': 1.0,
                    'price_unit': line_amount,
                    'analytic_distribution': analytic_distribution or False,
                }
                if tax_ids:
                    vals['tax_ids'] = tax_ids
                lines.append((0, 0, vals))
            return lines

        return [(0, 0, {
            'name': '%s — %s' % (product_tmpl.name, invoice_number),
            'account_id': self.account_id.id,
            'quantity': 1.0,
            'price_unit': effective_amount,
            'analytic_distribution': analytic_distribution or False,
        })]

    # ── Paiement et rapprochement ─────────────────────────────────────────────

    def _register_and_reconcile_payment(self, move, parsed_data):
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

        payment_date = (
            parsed_data['invoice_date']
            if self.payment_date_source == 'invoice_date'
            else date.today()
        )

        memo_template = self.payment_memo or 'Règlement {invoice_number}'
        memo = memo_template.format(
            invoice_number=parsed_data.get('invoice_number', ''),
            contract_number=parsed_data.get('contract_number', ''),
            partner=self.partner_id.name or '',
        )

        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner_id.id,
            'journal_id': self.payment_journal_id.id,
            'currency_id': move.currency_id.id,
            'amount': move.amount_residual,
            'date': payment_date,
            'ref': memo,
        })
        payment.action_post()

        _logger.info(
            "Paiement créé : %s — %.2f %s — %s",
            payment.name, move.amount_residual, self.currency_code, payment_date,
        )

        self._reconcile_move_and_payment(move, payment)

    def _reconcile_move_and_payment(self, move, payment):
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
                move.name, payment.name,
            )
            return

        try:
            to_reconcile.reconcile()
            _logger.info(
                "Rapprochement effectué : facture %s ↔ paiement %s",
                move.name, payment.name,
            )
        except Exception as exc:
            _logger.error(
                "_reconcile: erreur — %s / %s — %s",
                move.name, payment.name, exc,
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

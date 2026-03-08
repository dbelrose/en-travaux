# -*- coding: utf-8 -*-
"""
Assistant d'import manuel de fichiers .eml — v3

Supporte deux types de règles :
  • supplier.email.rule  → factures fournisseurs (account.move)
  • bank.alert.email.rule → alertes bancaires (account.bank.statement.line)
"""

import base64
import email as email_lib
import re
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.pdf_parser import extract_pdf_text, PDF_AVAILABLE

_logger = logging.getLogger(__name__)


class ImportEmlLine(models.TransientModel):
    """Ligne de résultat d'import dans le wizard."""
    _name = 'import.eml.wizard.line'
    _description = 'Ligne de résultat import EML'

    wizard_id = fields.Many2one('import.eml.wizard', ondelete='cascade')
    filename = fields.Char(string='Fichier')

    # Type de résultat
    rule_type = fields.Selection([
        ('supplier', 'Facture fournisseur'),
        ('bank', 'Alerte bancaire'),
    ], string='Type', default='supplier')

    status = fields.Selection([
        ('ok', 'Importé'),
        ('duplicate', 'Doublon'),
        ('error', 'Erreur'),
    ], string='Statut')
    message = fields.Char(string='Détail')

    # Facture fournisseur
    move_id = fields.Many2one('account.move', string='Facture créée')
    invoice_number = fields.Char(string='N° Facture')
    contract_number = fields.Char(string='N° Contrat')
    amount = fields.Float(string='Montant')
    supplier_rule_id = fields.Many2one('supplier.email.rule', string='Règle fournisseur')
    parsing_source = fields.Selection([
        ('body', 'Corps email'),
        ('pdf', 'Pièce jointe PDF'),
        ('mixed', 'Corps + PDF'),
    ], string='Source parsing', readonly=True)
    pdf_lines_count = fields.Integer(string='Lignes PDF', readonly=True)
    payment_registered = fields.Boolean(string='Paiement enregistré', readonly=True)

    # Alerte bancaire
    bank_rule_id = fields.Many2one('bank.alert.email.rule', string='Règle bancaire')
    bank_lines_created = fields.Integer(string='Opérations créées', readonly=True)
    bank_lines_duplicate = fields.Integer(string='Doublons', readonly=True)
    bank_lines_reconciled = fields.Integer(string='Rapprochées', readonly=True)


class ImportEmlWizard(models.TransientModel):
    """
    Assistant d'import de fichiers .eml.
    Supporte les factures fournisseurs et les alertes bancaires.
    """
    _name = 'import.eml.wizard'
    _description = 'Assistant import factures email (.eml)'

    # ── Champs principaux ────────────────────────────────────────────────────

    attachment_ids = fields.Many2many(
        'ir.attachment',
        'import_eml_wiz_att_rel',
        'wizard_id', 'att_id',
        string='Pièces jointes uploadées',
    )

    rule_id = fields.Many2one(
        'supplier.email.rule',
        string='Règle fournisseur (optionnel)',
        help="Force l'utilisation d'une règle fournisseur spécifique."
    )
    bank_rule_id = fields.Many2one(
        'bank.alert.email.rule',
        string='Règle bancaire (optionnel)',
        help="Force l'utilisation d'une règle d'alerte bancaire spécifique."
    )

    # ── Résultats ────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Prêt'),
        ('done', 'Terminé'),
    ], default='draft')

    result_line_ids = fields.One2many(
        'import.eml.wizard.line', 'wizard_id', string='Résultats'
    )
    result_ok_count = fields.Integer(string='Importés', compute='_compute_counts')
    result_dup_count = fields.Integer(string='Doublons', compute='_compute_counts')
    result_err_count = fields.Integer(string='Erreurs', compute='_compute_counts')

    pdf_available = fields.Boolean(
        string='Moteur PDF disponible',
        compute='_compute_pdf_available',
    )

    @api.depends()
    def _compute_pdf_available(self):
        for wiz in self:
            wiz.pdf_available = PDF_AVAILABLE

    @api.depends('result_line_ids.status')
    def _compute_counts(self):
        for wiz in self:
            lines = wiz.result_line_ids
            wiz.result_ok_count = len(lines.filtered(lambda l: l.status == 'ok'))
            wiz.result_dup_count = len(lines.filtered(lambda l: l.status == 'duplicate'))
            wiz.result_err_count = len(lines.filtered(lambda l: l.status == 'error'))

    # ── Détection de règle ───────────────────────────────────────────────────

    def _detect_supplier_rule(self, msg):
        """Détecte une règle fournisseur depuis l'expéditeur/sujet."""
        sender = msg.get('From', '')
        subject = msg.get('Subject', '')
        rules = self.env['supplier.email.rule'].search([('active', '=', True)])
        for rule in rules:
            if not rule.sender_email_pattern:
                continue
            if re.search(rule.sender_email_pattern, sender, re.IGNORECASE):
                if rule.subject_pattern:
                    if re.search(rule.subject_pattern, subject, re.IGNORECASE):
                        return rule
                    continue
                return rule
        return None

    def _detect_bank_rule(self, msg):
        """Détecte une règle d'alerte bancaire depuis l'expéditeur/sujet."""
        sender = msg.get('From', '')
        subject = msg.get('Subject', '')
        rules = self.env['bank.alert.email.rule'].search([('active', '=', True)])
        for rule in rules:
            if not rule.sender_email_pattern:
                continue
            if re.search(rule.sender_email_pattern, sender, re.IGNORECASE):
                if rule.subject_pattern:
                    if re.search(rule.subject_pattern, subject, re.IGNORECASE):
                        return rule
                    continue
                return rule
        return None

    # ── Extraction du corps texte ─────────────────────────────────────────────

    @staticmethod
    def _get_text_body(msg):
        """Extrait le corps texte brut d'un message email."""
        body = ''
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                body += payload.decode(charset, errors='replace')
        if body.strip():
            return body

        # Fallback : décodage HTML
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                html = payload.decode(charset, errors='replace')
                # Nettoyage HTML basique
                clean = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
                clean = re.sub(r'<[^>]+>', ' ', clean)
                clean = (clean
                         .replace('&amp;', '&').replace('&lt;', '<')
                         .replace('&gt;', '>').replace('&nbsp;', ' ')
                         .replace('&#160;', ' ').replace('&#8239;', ' '))
                clean = clean.replace('\u00a0', ' ').replace('\u202f', ' ')
                clean = re.sub(r'[ \t]+', ' ', clean)
                clean = re.sub(r'\n{3,}', '\n\n', clean)
                body += clean
        return body

    @staticmethod
    def _get_pdf_attachments(msg):
        """Extrait toutes les pièces jointes PDF d'un message email."""
        pdfs = []
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = part.get('Content-Disposition', '')
            filename = part.get_filename() or ''
            is_pdf = (
                content_type == 'application/pdf'
                or 'pdf' in content_type.lower()
                or filename.lower().endswith('.pdf')
            )
            is_attachment = (
                'attachment' in content_disposition.lower()
                or 'inline' in content_disposition.lower()
                or filename
            )
            if is_pdf and is_attachment:
                payload = part.get_payload(decode=True)
                if payload:
                    pdfs.append((filename, payload))
        return pdfs

    # ── Traitement d'un .eml (fournisseur) ───────────────────────────────────

    def _process_eml_supplier(self, msg, rule, filename):
        """Traite un email comme une facture fournisseur."""
        body_text = self._get_text_body(msg)
        pdf_attachments = self._get_pdf_attachments(msg)
        pdf_text = ''
        parsing_source = 'body'

        if rule.use_pdf_attachment and pdf_attachments:
            for pdf_filename, pdf_bytes in pdf_attachments:
                try:
                    extracted = extract_pdf_text(pdf_bytes)
                    if extracted.strip():
                        pdf_text = extracted
                        break
                except Exception as exc:
                    _logger.warning(
                        "_process_eml_supplier: erreur PDF '%s' — %s",
                        pdf_filename, exc
                    )
            if pdf_text:
                if rule.pdf_prefer_over_body:
                    parsing_text = pdf_text
                    parsing_source = 'pdf'
                else:
                    parsing_text = (body_text + '\n\n' + pdf_text).strip()
                    parsing_source = 'mixed'
            else:
                parsing_text = body_text
        else:
            parsing_text = body_text

        if not parsing_text:
            return {
                'filename': filename, 'rule_type': 'supplier',
                'status': 'error',
                'message': _("Corps texte de l'email introuvable."),
                'supplier_rule_id': rule.id,
            }

        try:
            parsed = rule._parse_email_body(parsing_text)
        except UserError as e:
            return {
                'filename': filename, 'rule_type': 'supplier',
                'status': 'error', 'message': str(e),
                'supplier_rule_id': rule.id,
                'parsing_source': parsing_source,
            }

        pdf_lines = []
        if rule.use_pdf_attachment and rule.pdf_extract_lines and pdf_text:
            try:
                pdf_lines = rule._parse_pdf_lines(pdf_text)
            except UserError as exc:
                _logger.warning("_process_eml_supplier: lignes PDF — %s", exc)

        try:
            move, created = rule.create_vendor_bill(parsed, pdf_lines=pdf_lines)
        except UserError as e:
            return {
                'filename': filename, 'rule_type': 'supplier',
                'status': 'error', 'message': str(e),
                'supplier_rule_id': rule.id,
                'invoice_number': parsed.get('invoice_number'),
                'contract_number': parsed.get('contract_number'),
                'amount': parsed.get('amount'),
                'parsing_source': parsing_source,
            }

        payment_registered = (
            created and rule.auto_post_bill and rule.auto_register_payment
            and move.payment_state in ('paid', 'in_payment', 'partial')
        )

        return {
            'filename': filename, 'rule_type': 'supplier',
            'status': 'ok' if created else 'duplicate',
            'message': move.name if created else _("Déjà importé : %s") % move.name,
            'move_id': move.id,
            'supplier_rule_id': rule.id,
            'invoice_number': parsed['invoice_number'],
            'contract_number': parsed['contract_number'],
            'amount': parsed['amount'],
            'parsing_source': parsing_source if created else False,
            'pdf_lines_count': len(pdf_lines),
            'payment_registered': payment_registered,
        }

    # ── Traitement d'un .eml (alerte bancaire) ────────────────────────────────

    def _process_eml_bank_alert(self, msg, rule, filename):
        """Traite un email comme une alerte bancaire."""
        body_text = self._get_text_body(msg)

        if not body_text.strip():
            return {
                'filename': filename, 'rule_type': 'bank',
                'status': 'error',
                'message': _("Corps texte de l'email introuvable."),
                'bank_rule_id': rule.id,
            }

        try:
            results = rule.process_bank_alert(body_text)
        except UserError as e:
            return {
                'filename': filename, 'rule_type': 'bank',
                'status': 'error', 'message': str(e),
                'bank_rule_id': rule.id,
            }

        created = sum(1 for r in results if r.get('created'))
        duplicates = sum(1 for r in results if not r.get('created') and not r.get('error'))
        reconciled = sum(1 for r in results if r.get('reconciled'))
        errors = sum(1 for r in results if r.get('error'))

        if errors and not created and not duplicates:
            return {
                'filename': filename, 'rule_type': 'bank',
                'status': 'error',
                'message': results[0].get('error', _("Erreur inconnue")),
                'bank_rule_id': rule.id,
            }

        total = len(results)
        msg_parts = []
        if created:
            msg_parts.append("%d/%d opération(s) créée(s)" % (created, total))
        if duplicates:
            msg_parts.append("%d doublon(s)" % duplicates)
        if reconciled:
            msg_parts.append("%d rapprochée(s)" % reconciled)
        if errors:
            msg_parts.append("%d erreur(s)" % errors)

        return {
            'filename': filename, 'rule_type': 'bank',
            'status': 'ok' if created else ('duplicate' if duplicates else 'error'),
            'message': ' — '.join(msg_parts),
            'bank_rule_id': rule.id,
            'bank_lines_created': created,
            'bank_lines_duplicate': duplicates,
            'bank_lines_reconciled': reconciled,
        }

    # ── Traitement principal d'un .eml ────────────────────────────────────────

    def _process_eml_bytes(self, raw_bytes, filename):
        """Détecte le type de règle et dispatch vers le bon traitement."""
        try:
            msg = email_lib.message_from_bytes(raw_bytes)
        except Exception as e:
            return {
                'filename': filename, 'status': 'error',
                'message': _("Impossible de lire le fichier EML : %s") % str(e),
            }

        # Priorité : règle forcée dans le wizard
        if self.bank_rule_id:
            return self._process_eml_bank_alert(msg, self.bank_rule_id, filename)
        if self.rule_id:
            return self._process_eml_supplier(msg, self.rule_id, filename)

        # Détection automatique — on teste d'abord les règles bancaires,
        # puis les règles fournisseurs (les alertes bancaires ont rarement
        # le même expéditeur qu'un fournisseur)
        bank_rule = self._detect_bank_rule(msg)
        if bank_rule:
            return self._process_eml_bank_alert(msg, bank_rule, filename)

        supplier_rule = self._detect_supplier_rule(msg)
        if supplier_rule:
            return self._process_eml_supplier(msg, supplier_rule, filename)

        return {
            'filename': filename, 'status': 'error',
            'message': _("Aucune règle de parsing ne correspond à cet email "
                         "(expéditeur : %s).") % msg.get('From', '?'),
        }

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_import(self):
        """Lance l'import de tous les fichiers attachés."""
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("Veuillez d'abord joindre au moins un fichier .eml."))

        results = []
        for att in self.attachment_ids:
            raw = base64.b64decode(att.datas)
            res = self._process_eml_bytes(raw, att.name)
            results.append(res)

        self.result_line_ids.unlink()
        self.write({
            'result_line_ids': [(0, 0, r) for r in results],
            'state': 'done',
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.eml.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_bills(self):
        """Ouvre la liste des factures créées lors de cet import."""
        self.ensure_one()
        move_ids = self.result_line_ids.filtered(
            lambda l: l.move_id
        ).mapped('move_id').ids
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'domain': [('id', 'in', move_ids)],
            'view_mode': 'list,form',
            'name': _('Factures importées'),
            'target': 'current',
        }

    def action_view_bank_lines(self):
        """Ouvre les lignes de relevé bancaire créées lors de cet import."""
        self.ensure_one()
        bank_rule_ids = self.result_line_ids.filtered(
            lambda l: l.bank_rule_id
        ).mapped('bank_rule_id').ids
        if not bank_rule_ids:
            raise UserError(_("Aucune ligne de relevé bancaire créée."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.bank.statement.line',
            'domain': [
                ('narration', 'ilike', "Règle '"),
            ],
            'view_mode': 'list,form',
            'name': _('Relevé bancaire importé'),
            'target': 'current',
        }

    def action_reset(self):
        """Remet le wizard en état initial."""
        self.ensure_one()
        self.result_line_ids.unlink()
        self.write({
            'state': 'draft',
            'attachment_ids': [(5, 0, 0)],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.eml.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

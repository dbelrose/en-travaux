# -*- coding: utf-8 -*-
"""
Assistant d'import manuel de fichiers .eml.

Extension v2 :
  • Extraction et transmission des pièces jointes PDF au moteur de règle
  • Affichage du mode de parsing utilisé (corps / PDF / mixte)
  • Résultats enrichis : lignes PDF extraites, état paiement
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
    status = fields.Selection([
        ('ok', 'Importé'),
        ('duplicate', 'Doublon'),
        ('error', 'Erreur'),
    ], string='Statut')
    message = fields.Char(string='Détail')
    move_id = fields.Many2one('account.move', string='Facture créée')
    invoice_number = fields.Char(string='N° Facture')
    contract_number = fields.Char(string='N° Contrat')
    amount = fields.Float(string='Montant')
    rule_id = fields.Many2one('supplier.email.rule', string='Règle utilisée')
    parsing_source = fields.Selection([
        ('body', 'Corps email'),
        ('pdf', 'Pièce jointe PDF'),
        ('mixed', 'Corps + PDF'),
    ], string='Source parsing', readonly=True)
    pdf_lines_count = fields.Integer(string='Lignes PDF', readonly=True)
    payment_registered = fields.Boolean(string='Paiement enregistré', readonly=True)


class ImportEmlWizard(models.TransientModel):
    """
    Assistant d'import de fichiers .eml contenant des factures fournisseurs.
    Supporte l'import de plusieurs fichiers en une seule opération.
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
        string='Règle de parsing (optionnel)',
        help="Si non renseigné, la règle est détectée automatiquement "
             "depuis l'adresse expéditeur de chaque email."
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

    def _detect_rule(self, msg):
        """Détecte la règle à appliquer depuis l'expéditeur/sujet du message."""
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
        return body

    # ── Extraction des pièces jointes PDF depuis le message .eml ─────────────

    @staticmethod
    def _get_pdf_attachments(msg):
        """
        Extrait toutes les pièces jointes PDF d'un message email (email.message).

        Returns:
            list of (filename: str, content: bytes)
        """
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

    # ── Traitement d'un .eml ─────────────────────────────────────────────────

    def _process_eml_bytes(self, raw_bytes, filename):
        """
        Traite un fichier .eml (bytes).
        Retourne un dict de résultat à stocker dans result_line_ids.
        """
        try:
            msg = email_lib.message_from_bytes(raw_bytes)
        except Exception as e:
            return {
                'filename': filename,
                'status': 'error',
                'message': _("Impossible de lire le fichier EML : %s") % str(e),
            }

        # Détection de la règle
        rule = self.rule_id or self._detect_rule(msg)
        if not rule:
            return {
                'filename': filename,
                'status': 'error',
                'message': _("Aucune règle de parsing ne correspond à cet email "
                             "(expéditeur : %s).") % msg.get('From', '?'),
            }

        # Extraction du corps texte
        body_text = self._get_text_body(msg)

        # Extraction des PDF joints
        pdf_attachments = self._get_pdf_attachments(msg)
        pdf_text = ''
        parsing_source = 'body'

        if rule.use_pdf_attachment and pdf_attachments:
            for pdf_filename, pdf_bytes in pdf_attachments:
                try:
                    extracted = extract_pdf_text(pdf_bytes)
                    if extracted.strip():
                        pdf_text = extracted
                        _logger.info(
                            "_process_eml_bytes: PDF '%s' extrait (%d caractères).",
                            pdf_filename, len(pdf_text)
                        )
                        break
                except Exception as exc:
                    _logger.warning(
                        "_process_eml_bytes: erreur PDF '%s' — %s",
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
                'filename': filename,
                'status': 'error',
                'message': _("Corps texte de l'email introuvable."),
                'rule_id': rule.id,
            }

        # Parsing principal
        try:
            parsed = rule._parse_email_body(parsing_text)
        except UserError as e:
            return {
                'filename': filename,
                'status': 'error',
                'message': str(e),
                'rule_id': rule.id,
                'parsing_source': parsing_source,
            }

        # Extraction des lignes de détail PDF
        pdf_lines = []
        if rule.use_pdf_attachment and rule.pdf_extract_lines and pdf_text:
            try:
                pdf_lines = rule._parse_pdf_lines(pdf_text)
            except UserError as exc:
                _logger.warning("_process_eml_bytes: lignes PDF — %s", exc)

        # Création de la facture
        try:
            move, created = rule.create_vendor_bill(parsed, pdf_lines=pdf_lines)
        except UserError as e:
            return {
                'filename': filename,
                'status': 'error',
                'message': str(e),
                'rule_id': rule.id,
                'invoice_number': parsed.get('invoice_number'),
                'contract_number': parsed.get('contract_number'),
                'amount': parsed.get('amount'),
                'parsing_source': parsing_source,
            }

        # Déterminer si un paiement a été enregistré
        payment_registered = (
            created and rule.auto_post_bill and rule.auto_register_payment
            and move.payment_state in ('paid', 'in_payment', 'partial')
        )

        return {
            'filename': filename,
            'status': 'ok' if created else 'duplicate',
            'message': move.name if created else _("Déjà importé : %s") % move.name,
            'move_id': move.id,
            'rule_id': rule.id,
            'invoice_number': parsed['invoice_number'],
            'contract_number': parsed['contract_number'],
            'amount': parsed['amount'],
            'parsing_source': parsing_source if created else False,
            'pdf_lines_count': len(pdf_lines),
            'payment_registered': payment_registered,
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

    def action_reset(self):
        """Remet le wizard en état initial."""
        self.ensure_one()
        self.result_line_ids.unlink()
        self.write({'state': 'draft', 'attachment_ids': [(5, 0, 0)]})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.eml.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

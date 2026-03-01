# -*- coding: utf-8 -*-
import base64
import email as email_lib
import re
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError

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


class ImportEmlWizard(models.TransientModel):
    """
    Assistant d'import de fichiers .eml contenant des factures fournisseurs.
    Supporte l'import de plusieurs fichiers en une seule opération.
    """
    _name = 'import.eml.wizard'
    _description = 'Assistant import factures email (.eml)'

    # ── Champs principaux ────────────────────────────────────────────────────

    eml_file_ids = fields.Many2many(
        'ir.attachment',
        string='Fichiers .eml',
        help="Sélectionnez un ou plusieurs fichiers .eml reçus de votre fournisseur."
    )

    # Upload multi-fichier via le widget binary
    eml_data = fields.Binary(string='Fichier .eml (upload)')
    eml_filename = fields.Char(string='Nom du fichier')

    # Fichiers uploadés (stockés temporairement)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'import_eml_wiz_att_rel',
        'wizard_id',
        'att_id',
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
        'import.eml.wizard.line',
        'wizard_id',
        string='Résultats',
    )
    result_ok_count = fields.Integer(
        string='Importés', compute='_compute_counts'
    )
    result_dup_count = fields.Integer(
        string='Doublons', compute='_compute_counts'
    )
    result_err_count = fields.Integer(
        string='Erreurs', compute='_compute_counts'
    )

    @api.depends('result_line_ids.status')
    def _compute_counts(self):
        for wiz in self:
            lines = wiz.result_line_ids
            wiz.result_ok_count = len(lines.filtered(lambda l: l.status == 'ok'))
            wiz.result_dup_count = len(lines.filtered(lambda l: l.status == 'duplicate'))
            wiz.result_err_count = len(lines.filtered(lambda l: l.status == 'error'))

    # ── Logique ──────────────────────────────────────────────────────────────

    def _detect_rule(self, msg):
        """
        Détecte automatiquement la règle à appliquer en testant le pattern
        expéditeur de chaque règle active.
        """
        sender = msg.get('From', '')
        subject = msg.get('Subject', '')
        rules = self.env['supplier.email.rule'].search([('active', '=', True)])
        for rule in rules:
            if re.search(rule.sender_email_pattern, sender, re.IGNORECASE):
                if rule.subject_pattern:
                    if re.search(rule.subject_pattern, subject, re.IGNORECASE):
                        return rule
                    else:
                        continue
                return rule
        return None

    @staticmethod
    def _get_text_body(msg):
        """Extrait le corps texte brut d'un message email."""
        body = ''
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == 'text/plain':
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                body += payload.decode(charset, errors='replace')
        return body

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
        body = self._get_text_body(msg)
        if not body:
            return {
                'filename': filename,
                'status': 'error',
                'message': _("Corps texte de l'email introuvable."),
                'rule_id': rule.id,
            }

        # Parsing
        try:
            parsed = rule._parse_email_body(body)
        except UserError as e:
            return {
                'filename': filename,
                'status': 'error',
                'message': str(e),
                'rule_id': rule.id,
            }

        # Création de la facture
        try:
            move, created = rule.create_vendor_bill(parsed)
        except UserError as e:
            return {
                'filename': filename,
                'status': 'error',
                'message': str(e),
                'rule_id': rule.id,
                'invoice_number': parsed.get('invoice_number'),
                'contract_number': parsed.get('contract_number'),
                'amount': parsed.get('amount'),
            }

        return {
            'filename': filename,
            'status': 'ok' if created else 'duplicate',
            'message': move.name if created else _(
                "Déjà importé : %s") % move.name,
            'move_id': move.id,
            'rule_id': rule.id,
            'invoice_number': parsed['invoice_number'],
            'contract_number': parsed['contract_number'],
            'amount': parsed['amount'],
        }

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

        # Supprimer les anciennes lignes
        self.result_line_ids.unlink()

        # Créer les nouvelles lignes
        line_vals = []
        for r in results:
            line_vals.append((0, 0, r))
        self.write({
            'result_line_ids': line_vals,
            'state': 'done',
        })

        # Rouvrir le wizard pour afficher les résultats
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

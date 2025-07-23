import base64
import csv
import logging
from datetime import datetime
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class BankStatementImportPaierie(models.TransientModel):
    _name = 'bank.statement.import.paierie'
    _description = 'Importation de lignes de relevés bancaires de la Pairie'

    file_data = fields.Binary(string="Fichier CSV", required=True)
    file_name = fields.Char(string="Nom du fichier")

    def _convert_date(self, date_str):
        """Convertit une date du format DD/MM/YYYY au format ISO (YYYY-MM-DD)."""
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError(f"Format de date invalide : {date_str}. Utilisez le format DD/MM/YYYY.")

    def _create_attachment(self, statement):
        """Crée une pièce jointe du fichier importé dans le chatter du relevé"""
        if not self.file_data:
            return

        # Créer la pièce jointe
        attachment = self.env['ir.attachment'].create({
            'name': statement.name,
            'datas': self.file_content,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'text/csv',
        })

        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Fichier d'import CCP : {self.file_name}",
            attachment_ids=[attachment.id],
            subject="Import de relevé bancaire CCP"
        )

    def _create_pdf_attachment(self, statement):
        """Crée une pièce jointe PDF du relevé bancaire dans le chatter"""
        if not statement:
            return

        try:
            # Générer le rapport PDF du relevé bancaire
            report = self.env.ref('account.action_report_account_statement')
            pdf_content, _ = report._render_qweb_pdf([statement.id])

            # Encoder le contenu PDF en base64
            pdf_data = base64.b64encode(pdf_content)

            # Créer la pièce jointe PDF
            pdf_attachment = self.env['ir.attachment'].create({
                'name': f"{statement.name}.pdf",
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé bancaire généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject="Relevé bancaire CCP (PDF)"
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None

    def action_bank_statement_import_paierie(self):
        """Importe les données du fichier CSV dans account.bank.statement.line."""
        # Décodage du fichier
        global statement
        file_content = base64.b64decode(self.file_data).decode('utf-8')
        csv_reader = csv.DictReader(file_content.splitlines())

        move_ids = []

        for row in csv_reader:
            # Conversion de la date
            date_iso = self._convert_date(row.get('DATE', '').strip())

            # Calcul du montant (CREDIT - DEBIT)
            credit = float(row.get('CREDIT', 0) or 0)
            debit = float(row.get('DEBIT', 0) or 0)
            amount = credit - debit

            # Création du journal et relevé bancaire
            journal = self.env['account.journal'].search([('code', '=', 'PF')], limit=1)
            if not journal:
                journal = self.env['account.journal'].create({
                    'name': 'Journal PF',
                    'code': 'PF',
                    'type': 'bank',
                })

            statement = self.env['account.bank.statement'].search([
                ('journal_id', '=', journal.id),
                ('date', '=', date_iso)
            ], limit=1)

            if not statement:
                statement = self.env['account.bank.statement'].create({
                    'journal_id': journal.id,
                    'date': date_iso,
                })

            # Mapping des champs de la ligne
            line_vals = {
                'statement_id': statement.id,  # Relier la ligne au relevé bancaire
                'date': date_iso,  # Date convertie
                'payment_ref': f"{row.get('JOURNAL', '')} - {row.get('LIBELLE', '')}",  # Référence de paiement
                'ref': f"{row.get('JOURNAL', '')} - {row.get('LIBELLE', '')}",  # Référence de paiement
                'amount': amount,  # Montant calculé
            }

            # Créer la ligne du relevé bancaire
            line = self.env['account.bank.statement.line'].create(line_vals)
            move_ids.append(line.id)

        # Ajouter les fichiers en pièce jointe dans le chatter
        self._create_attachment(statement)  # Fichier existant
        self._create_pdf_attachment(statement)  # PDF nouveau

        # Retourner une action pour afficher la vue en liste filtrée
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importation réussie des bordereaux de recettes Paierie',
            'context': {'create': False},
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }

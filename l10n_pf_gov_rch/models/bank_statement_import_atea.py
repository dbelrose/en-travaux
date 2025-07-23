import csv
import base64
import logging
from datetime import datetime
from odoo import models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankStatementImportAtea(models.TransientModel):
    _name = 'bank.statement.import.atea'
    _description = 'Import Bank Statements'

    file_data = fields.Binary(string='Fichier CSV', required=True)
    file_name = fields.Char(string='Nom du fichier')

    def _get_journal(self, journal_code):
        """Récupère le journal par son code"""
        journal = self.env['account.journal'].search([('code', '=', journal_code)], limit=1)
        if not journal:
            raise UserError(f"Journal introuvable pour le code: {journal_code}")
        return journal

    def _display_import_result(self, statements):
        """Affiche le résultat de l'importation"""
        statement_ids = [statement.id for statement in statements]

    # Retourne une action Odoo pour afficher les mouvements importés
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importation réussie du relevé Atea',
            'res_model': 'account.bank.statement',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', statement_ids)],
            'target': 'current',
        }

    def _create_attachment(self, statement):
        """Crée une pièce jointe du fichier importé dans le chatter du relevé"""
        if not self.file_data:
            return

        # Créer la pièce jointe
        attachment = self.env['ir.attachment'].create({
            'name': f"{statement.name}.csv",
            'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_atea').id])],
            'datas': self.file_data,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'text/csv',
        })

        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Relevé Atea importé : {statement.name}.csv",
            attachment_ids=[attachment.id],
            subject=f"Relevé Atea importé : {statement.name}.csv",
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
                'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_atea').id])],
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé Atea généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject=f"Relevé Atea généré : {statement.name}.pdf",
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None

    def action_bank_statement_import_atea(self):
        # Décodage du fichier CSV
        try:
            file_content = base64.b64decode(self.file_data).decode('utf-8')
        except Exception as e:
            raise ValueError(
                "Erreur lors du décodage du fichier. Vérifiez que le fichier est au format attendu.") from e

        data_lines = file_content.splitlines()
        reader = csv.reader(data_lines, delimiter=';')

        statements = []

        # Grouper les lignes par journal et date pour créer un relevé unique par journal/date
        statement_groups = {}

        for row in reader:
            # Ignorer les lignes vides
            if not any(row):
                continue

            try:
                # Remplissage manuel si colonnes manquantes
                try:
                    journal_code, reference, amount_str, date_str, *rest = row
                    dom_enr = rest[0] if rest else 'DOM'
                except Exception as e:
                    raise ValueError(f"Erreur de formatage des données dans la ligne: {row}. Erreur: {e}")

                amount = float(amount_str)  # Montant en XPF (pas de décimales)
                date = datetime.strptime(date_str, '%d/%m/%Y').date()

                # Clé pour grouper les lignes par journal et date
                group_key = (journal_code, date)

                if group_key not in statement_groups:
                    statement_groups[group_key] = []

                statement_groups[group_key].append({
                    'reference': reference,
                    'amount': amount,
                    'date': date,
                    'dom_enr': dom_enr,
                })

            except ValueError as e:
                raise UserError(f'Erreur de formatage des données dans la ligne: {row}. Erreur: {str(e)}')

        # Créer les relevés bancaires
        for (journal_code, date), lines in statement_groups.items():
            journal = self._get_journal(journal_code)

            # Créer un nom unique pour le relevé
            statement_name = f"CHQ {journal_code} du {date.strftime('%d/%m/%Y')}"

            # Préparer les lignes du relevé (structure simplifiée pour Odoo 14)
            line_vals = []
            for line in lines:
                line_vals.append((0, 0, {
                    'payment_ref': f"CHQ {journal_code} n° {line['reference']} - {line['dom_enr']}",
                    'ref': f"CHQ {journal_code} n° {line['reference']} - {line['dom_enr']}",
                    'amount': line['amount'],
                    'date': date,
                    # En Odoo 14, on ne spécifie pas counterpart_account_id dans la création
                    # L'utilisateur devra faire la réconciliation manuellement
                }))

            # Créer le relevé bancaire
            statement = self.env['account.bank.statement'].create({
                'journal_id': journal.id,
                'date': date,
                'name': statement_name,
                'line_ids': line_vals
            })
            statements.append(statement)

            # Ajouter les fichiers en pièce jointe dans le chatter
            self._create_attachment(statement)  # Fichier existant
            self._create_pdf_attachment(statement)  # PDF nouveau

        return self._display_import_result(statements)

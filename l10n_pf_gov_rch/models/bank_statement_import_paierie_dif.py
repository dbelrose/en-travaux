import base64
import csv
import logging
from datetime import datetime
from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class BankStatementImportPaierieDIF(models.TransientModel):
    _name = 'bank.statement.import.paierie.dif'
    _description = 'Importation de fichiers DIF pour la comptabilité'

    # file_data = fields.Binary(string="Fichier DIF", required=True)
    file_data = fields.Binary(
        string="Fichier DIF",
        required=True,
        help="Sélectionnez un fichier avec l'extension .dif uniquement.",
        attachment=True  # Optionnel : pour forcer la création d'une pièce jointe
    )

    file_name = fields.Char(string="Nom du fichier")

    def _parse_dif_file(self, file_content):
        """Analyse le fichier DIF et retourne une liste de dict contenant les données."""
        lines = file_content.splitlines()

        # Ignorer la première ligne (en-têtes)
        if not lines:
            raise UserError(_("Le fichier est vide."))
        header = lines[0]  # Ligne d'en-têtes
        data_lines = lines[1:]  # Lignes de données

        transactions = []
        first_transaction_date = None  # Variable pour stocker la première date

        for line in data_lines:
            # Analyser chaque ligne, en supposant un séparateur de tabulation (\t)
            fields = line.split("\t")
            if len(fields) < 12:  # Vérifier qu'il y a au moins 12 colonnes
                continue

            try:
                # Extraire les colonnes nécessaires
                raw_date = fields[7].strip()  # Colonne 8 (index 7)
                libelle = fields[10].strip()  # Colonne 10 (index 9)
                debit = float(fields[11].strip() or 0)  # Colonne 11 (index 10)
                credit = float(fields[12].strip() or 0)  # Colonne 12 (index 11)

                # Conversion de la date
                try:
                    date = datetime.strptime(raw_date, "%d/%m/%Y").date()
                except ValueError:
                    raise UserError(_("Format de date invalide dans le fichier : %s") % raw_date)

                # Créer une transaction
                transaction = {
                    'date': date,
                    'name': libelle,
                    'debit': debit,
                    'credit': credit,
                }
                transactions.append(transaction)

                # Capturer la date de la première transaction
                if first_transaction_date is None:
                    first_transaction_date = date
            except (ValueError, IndexError) as e:
                raise UserError(_("Erreur lors de l'analyse d'une ligne : %s") % e)

        return transactions, first_transaction_date
    def _create_attachment(self, statement):
        """Crée une pièce jointe du fichier importé dans le chatter du relevé"""
        if not self.file_data:
            return

        # Créer la pièce jointe
        attachment = self.env['ir.attachment'].create({
            'name': f"{statement.name}.dif",
            'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_paierie').id])],
            'datas': self.file_data,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'text/dif',
        })

        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Relevé Paierie importé : {statement.name}.dif",
            attachment_ids=[attachment.id],
            subject=f"Relevé Paierie importé : {statement.name}.dif",
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
                'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_paierie').id])],
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé Paierie généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject=f"Relevé Paierie généré : {statement.name}.pdf",
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None


    def action_bank_statement_import_pf(self):
        """Importe le fichier DIF et crée les lignes dans un relevé bancaire."""
        global statement

        if not self.file_data:
            raise UserError(_("Veuillez sélectionner un fichier DIF à importer."))

        # Décodage du fichier
        file_content = base64.b64decode(self.file_data).decode('windows-1252')
        csv_reader = csv.reader(file_content.splitlines(), delimiter='\t')

        # Analyse des transactions et récupération de la première date
        transactions, first_transaction_date = self._parse_dif_file(file_content)
        if not transactions:
            raise UserError(_("Aucune transaction valide n'a été trouvée dans le fichier."))

        # Création du journal et relevé bancaire
        journal = self.env['account.journal'].search([('code', '=', 'PF')], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'Journal PF',
                'code': 'PF',
                'type': 'bank',
            })

        # Ajout des lignes de relevé bancaire
        for transaction in transactions:
            date = transaction['date']

            statement = self.env['account.bank.statement'].search([
                ('journal_id', '=', journal.id),
                ('date', '=', date)
            ], limit=1)

            if not statement:
                statement = self.env['account.bank.statement'].create({
                    'journal_id': journal.id,
                    'date': date,
                    'name': f"Relevé Paierie {date.strftime('%Y%m%d')}",
                })

            self.env['account.bank.statement.line'].create({
                'date': date,
                'payment_ref': transaction['name'],
                'ref': transaction['name'],
                'amount': transaction['credit'] - transaction['debit'],  # Solde net
                'statement_id': statement.id,
            })

        # Ajouter les fichiers en pièce jointe dans le chatter
        self._create_attachment(statement)  # Fichier existant
        self._create_pdf_attachment(statement)  # PDF nouveau

        return {
            'type': 'ir.actions.act_window',
            'name': _('Relevé bancaire importé'),
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }

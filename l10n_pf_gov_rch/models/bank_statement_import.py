import base64
import csv
from odoo import models, fields, api, _


class BankStatementImport(models.TransientModel):
    _name = 'bank.statement.import'
    _description = 'Importation de relevés bancaires'

    file_data = fields.Binary(string="Fichier CSV", required=True)
    file_name = fields.Char(string="Nom du fichier")

    def action_import(self):
        """Importe les données du fichier CSV dans la table account.bank.statement."""
        # Décodage du fichier
        file_content = base64.b64decode(self.file_data).decode('utf-8')
        csv_reader = csv.DictReader(file_content.splitlines())

        for row in csv_reader:
            # Calcul du montant (CREDIT - DEBIT)
            credit = float(row.get('CREDIT', 0))
            debit = float(row.get('DEBIT', 0))
            amount = credit - debit

            # Mapping des champs
            statement_vals = {
                'invoice_date': row.get('DATE'),  # Date de la facture/transaction
                'payment_ref': f"{row.get('JOURNAL', '')} - {row.get('LIBELLE', '')}",  # Référence de paiement
                'amount': amount,  # Montant calculé
            }

            # Créer l'entrée dans account.bank.statement
            self.env['account.bank.statement'].create(statement_vals)

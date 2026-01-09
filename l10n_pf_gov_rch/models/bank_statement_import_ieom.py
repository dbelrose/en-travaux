import base64
import logging

from datetime import datetime
from bs4 import BeautifulSoup
from odoo import models, fields

_logger = logging.getLogger(__name__)


class BankStatementImportIEOM(models.TransientModel):
    _name = 'bank.statement.import.ieom'
    _description = 'Importation de lignes de relevés bancaires IEOM (HTML)'

    file_data = fields.Binary(string="Fichier HTML", required=True)
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
            'name': f"{statement.name}.csv",
            'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_ieom').id])],
            'datas': self.file_data,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'text/csv',
        })

        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Relevé IEOM importé : {statement.name}.csv",
            attachment_ids=[attachment.id],
            subject=f"Relevé IEOM importé : {statement.name}.csv",
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
                'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_ieom').id])],
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé IEOM généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject=f"Relevé IEOM généré : {statement.name}.pdf",
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None

    def action_bank_statement_import_ieom(self):
        """Importe les données du fichier HTML dans account.bank.statement.line."""
        # Décodage du fichier HTML
        global statement
        file_content = base64.b64decode(self.file_data).decode('windows-1252')
        soup = BeautifulSoup(file_content, 'html.parser')

        # Recherche des tableaux
        tables = soup.find_all('table')

        table = tables[-1] if tables else None

        if not table:
            raise ValueError("Aucun tableau trouvé dans le fichier HTML.")

        # Trouver toutes les lignes du 1er tableau
        rows = tables[0].find_all('tr')

        # Récupérer la date dans la cellule spécifique
        raw_date = rows[0].find_all('td')[3].get_text(strip=True)

        move_ids = []

        # Parcourir les lignes du tableau (en sautant l'en-tête)
        rows = tables[3].find_all('tr')
        headers = [header.text.strip() for header in rows[0].find_all('td')]

        for row in rows[1:]:  # Ignorer la ligne d'en-tête
            cells = row.find_all('td')

            # Vérifier que la ligne contient suffisamment de colonnes
            if len(cells) != len(headers):
                continue  # Ignorer les lignes incomplètes

            # Créer le dictionnaire des données
            data = {headers[i].strip(): cells[i].text.strip() for i in range(len(headers))}

            try:
                date_iso = self._convert_date(raw_date)  # Convertir la date au format ISO
            except ValueError as e:
                print(f"Erreur : {e}")

            try:
                # Lecture et traitement des données nécessaires
                montant_str = data["Montant"].replace('.', '')
                amount = float(montant_str)  # Conversion avec gestion des formats européens
                payment_ref = f"{data['Nom DO']} - {data['Libelle 1']}"
                if data.get('Libelle 2') and data['Libelle 2'].strip():
                    payment_ref += f"{data['Libelle 2'].strip()}"

                # Vérification ou création du journal
                journal = self.env['account.journal'].search([('code', '=', 'IEOM')], limit=1)
                if not journal:
                    journal = self.env['account.journal'].create({
                        'name': 'IEOM Journal',
                        'code': 'IEOM',
                        'type': 'bank',
                    })

                # Recherche ou création du relevé
                statement = self.env['account.bank.statement'].search([
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'open'),
                    ('date', '=', date_iso)
                ], limit=1)

                if not statement:
                    statement = self.env['account.bank.statement'].create({
                        'name': f"Relevé IEOM {date_iso.strftime('%Y%m%d')}",
                        'state': 'open',
                        'journal_id': journal.id,
                        'date': date_iso,
                    })

                # Rechercher ou créer la banque du contact
                bank_id = self.env['res.bank'].search([('bic', '=', data.get('Banque DO', ''))], limit=1)

                if not bank_id:
                    bank_id = self.env['res.bank'].create({
                        'bic': data.get('Banque DO', ''),
                        'name': data.get('Banque DO', ''),
                    })

                # Recherche ou création du contact
                partner_name = data.get('Nom DO', '')
                partner_id = self.env['res.partner'].search([('name', '=', partner_name)], limit=1)

                if not partner_id:
                    # Préparer les données bancaires si disponibles
                    bank_vals = []
                    if data.get('Banque DO') or data.get('Guichet DO') or data.get('Compte DO'):
                        bank_vals.append((0, 0, {
                            'bank_id': bank_id.id,  # Doit être un ID de res.bank
                            'acc_number': f"{data.get('Guichet DO', '')} - {data.get('Compte DO', '')}".strip(' -'),
                        }))

                    partner_id = self.env['res.partner'].create({
                        'name': partner_name,
                        'bank_ids': bank_vals,
                    })

                # Création de la ligne du relevé
                line = self.env['account.bank.statement.line'].create({
                    'date': date_iso,
                    'invoice_date': date_iso,
                    'ref': payment_ref,
                    'payment_ref': payment_ref,
                    'amount': amount,
                    'journal_id': journal.id,
                    'partner_id': partner_id.id,
                    'statement_id': statement.id,  # Associer à un relevé
                })
                move_ids.append(line.id)

                # Créer les enregistrements de paiement
                payment_vals = {
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': partner_id.id,  # Utiliser partner.id
                    'amount': amount,
                    'date': date_iso,
                    'journal_id': journal.id,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'ref': payment_ref,
                }
                self.env['account.payment'].create(payment_vals)

            except KeyError as e:
                raise ValueError(f"Champ manquant ou invalide dans le fichier HTML : {e}")

        # Ajouter les fichiers en pièce jointe dans le chatter
        self._create_attachment(statement)  # Fichier existant
        self._create_pdf_attachment(statement)  # PDF nouveau

        # Retourner une action pour afficher la vue en liste filtrée
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importation réussie des relevés bancaires IEOM',
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }
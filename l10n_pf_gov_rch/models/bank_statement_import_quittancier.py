import base64
import pandas as pd
import re
import logging

from odoo import models, fields

_logger = logging.getLogger(__name__)


class BankStatementImportQuittancier(models.TransientModel):
    _name = 'bank.statement.import.quittancier'
    _description = 'Importation de quittanciers depuis un fichier Excel'

    file_data = fields.Binary(string="Fichier Excel", required=True)
    file_name = fields.Char(string="Nom du fichier")

    def _create_attachment(self, statement):
        """Crée une pièce jointe du fichier importé dans le chatter du relevé"""
        if not self.file_data:
            return

        # Créer la pièce jointe
        attachment = self.env['ir.attachment'].create({
            'name': f"{statement.name}.xls",
            'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_cash').id])],
            'datas': self.file_data,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'application/vnd.ms-excel',
        })

        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Relevé Numéraire importé : {statement.name}.xls",
            attachment_ids=[attachment.id],
            subject=f"Relevé Numéraire importé : {statement.name}.xls",
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
                'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_cash').id])],
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé Numéraire généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject=f"Relevé Numéraire généré : {statement.name}.pdf",
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None

    def action_bank_statement_import_num(self):
        """Importe les données du fichier Excel dans account.bank.statement et account.bank.statement.line."""
        # Décodage et lecture du fichier Excel
        statement = None
        statement_ard = None
        file_content = base64.b64decode(self.file_data)
        temp_file_path = '/tmp/temp_quittancier.xlsx'
        with open(temp_file_path, 'wb') as temp_file:
            temp_file.write(file_content)

        # Lecture du fichier Excel avec pandas
        try:
            df = pd.read_excel(temp_file_path, parse_dates=True)
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier Excel : {e}")

        move_ids = []

        journal_code = 'NUM'

        # Vérification ou création d'un relevé bancaire parent
        journal = self.env['account.journal'].search([('code', '=', journal_code)], limit=1)
        if not journal:
            # if journal_code == 'NUM':
            journal = self.env['account.journal'].create({
                'code': 'NUM',
                'name': 'Numéraire',
                'type': 'cash',
            })
            # else:
            #     raise ValueError(f"Journal introuvable pour le code {journal_code}.")

        journal_code_ard = 'ARD'

        # Vérification ou création d'un relevé bancaire parent
        journal_ard = self.env['account.journal'].search([('code', '=', journal_code_ard)], limit=1)
        if not journal_ard:
            # if journal_code == journal_code_ard:
            journal_ard = self.env['account.journal'].create({
                'code': journal_code_ard,
                'name': 'Arrondis',
                'type': 'general',
            })
            # else:
            #     raise ValueError(f"Journal introuvable pour le code {journal_code_ard}.")

        ard_profit_account_id = journal_ard.profit_account_id  # 531
        ard_loss_account_id = journal_ard.loss_account_id  # 4788

        for _, row in df.iterrows():
            # Conversion de la date
            date_iso = row.get('Date', '')

            # Calcul du montant (CREDIT - DEBIT)
            amount = float(row.get('Encaissé', 0) or 0) + float(row.get('Arrondis', 0) or 0)
            amount_ard = float(row.get('Arrondis', 0) or 0)
            # End

            statement = self.env['account.bank.statement'].search([('journal_id', '=', journal.id),
                                                                   ('date', '=', date_iso)], limit=1)
            if not statement:
                statement = self.env['account.bank.statement'].create({
                    'date': date_iso,
                    'journal_id': journal.id,
                    'state': 'open',
                    'name': f"Relevé Numéraire {date_iso.strftime('%Y%m%d')}",
                })

            statement_ard = self.env['account.bank.statement'].search([('journal_id', '=', journal_ard.id),
                                                                       ('date', '=', date_iso)], limit=1)
            if not statement_ard:
                statement_ard = self.env['account.bank.statement'].create({
                    'date': date_iso,
                    'journal_id': journal_ard.id,
                    'state': 'open',
                    'name': f"Relevé Arrondis {date_iso.strftime('%Y%m%d')}",
                })

            payment_ref = f"{row.get('N° Dossier', '')} - {row.get('Nom du Demandeur', '')}"

            # Recherche ou création du contact
            partner_name = row.get('Nom du Demandeur', '').replace("DOM -", "").replace("DOM /", "") \
                .replace("CIP -", "").replace("CIP /", "").replace("ENR -", "").replace("- ENR", "") \
                .replace("- CA ENR", "").replace("CA ENR -", "").replace("[CA ENR]", "")
            partner_name = re.sub(r'\s+', ' ', partner_name.strip())
            partner_id = self.env['res.partner'].search([('name', '=', partner_name)], limit=1)

            if not partner_id:
                partner_id = self.env['res.partner'].create({
                    'name': partner_name,
                })

            # Mapping des champs de la ligne
            line_vals = {
                'date': date_iso,  # Date convertie
                'journal_id': journal.id,  # Journal
                'payment_ref': payment_ref,  # Référence de paiement
                'statement_id': statement.id,  # Relier la ligne au relevé bancaire
                'partner_id': partner_id.id,  # Relier au contact

                'amount': amount,  # Montant calculé
                'ref': f"{row.get('N° Dossier', '')} - {row.get('Nom du Demandeur', '')}",  # Référence de paiement
            }

            # Créer la ligne du relevé bancaire
            line = self.env['account.bank.statement.line'].create(line_vals)
            move_ids.append(line.id)

            if amount_ard > 0:
                # ✅ Cas d'un arrondi POSITIF → ligne de caisse classique

                line_vals_ard = {
                    'date': date_iso,  # Date convertie
                    'journal_id': journal_ard.id,  # Journal
                    'payment_ref': payment_ref,  # Référence de paiement
                    'statement_id': statement_ard.id,  # Relier la ligne au relevé bancaire

                    'amount': amount_ard,  # Montant calculé
                    'ref': f"{row.get('N° Dossier', '')} - {row.get('Nom du Demandeur', '')}",  # Référence de paiement
                }

                line_ard = self.env['account.bank.statement.line'].create(line_vals_ard)
                move_ids.append(line_ard.id)

            elif amount_ard < 0:
                # ✅ Cas d'un arrondi NEGATIF → écriture d'ajustement
                move_vals = {
                    'date': date_iso,
                    'journal_id': journal_ard.id,
                    'ref': f"Écart d'arrondi - {payment_ref}",
                    'line_ids': [
                        (0, 0, {
                            'account_id': ard_profit_account_id.id,  # Crédit caisse
                            'credit': abs(amount_ard),
                            'debit': 0.0,
                            'name': payment_ref,
                        }),
                        (0, 0, {
                            'account_id': ard_loss_account_id.id,  # Débit écart d’arrondi
                            'debit': abs(amount_ard),
                            'credit': 0.0,
                            'name': payment_ref,
                        }),
                    ],
                }
                move = self.env['account.move'].create(move_vals)
                move.post()

            # Créer les enregistrements de paiement
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.env['res.partner'].search([('name', '=', row.get('Nom du Demandeur', ''))],
                                                             limit=1).id,
                'amount': amount,
                'date': date_iso,
                'journal_id': journal.id,
                'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                'ref': f"{row.get('N° Dossier', '')} - {row.get('Nom du Demandeur', '')}",
            }
            self.env['account.payment'].create(payment_vals)

            if amount_ard > 0:
                payment_vals_ard = {
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': self.env['res.partner'].search([('name', '=', row.get('Nom du Demandeur', ''))],
                                                                 limit=1).id,
                    'amount': amount_ard,
                    'date': date_iso,
                    'journal_id': journal_ard.id,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'ref': f"{row.get('N° Dossier', '')} - {row.get('Nom du Demandeur', '')}",
                }
                self.env['account.payment'].create(payment_vals_ard)

        # Ajouter les fichiers en pièce jointe dans le chatter du relevé du numéraire
        if statement:
            self._create_attachment(statement)  # Fichier existant
            self._create_pdf_attachment(statement)  # PDF nouveau

        # Ajouter les fichiers en pièce jointe dans le chatter du relevé des arrondis
        if statement_ard:
            self._create_attachment(statement_ard)  # Fichier existant
            self._create_pdf_attachment(statement_ard)  # PDF nouveau

        # Retourner une action pour afficher la vue des quittanciers importés
        return {
            'type': 'ir.actions.act_window',
            'name': 'Importation réussie du relevé Quittancier',
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }

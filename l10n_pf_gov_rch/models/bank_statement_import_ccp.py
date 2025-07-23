import unicodedata
import base64
import csv
import logging
import re
from datetime import datetime
from odoo import models, fields

_logger = logging.getLogger(__name__)


class BankStatementImportCCP(models.TransientModel):
    _name = 'bank.statement.import.ccp'
    _description = 'Importation de lignes de relevés bancaires CCP'

    file_data = fields.Binary(string="Fichier CSV", required=True)
    file_name = fields.Char(string="Nom du fichier")

    def _get_last_two_words(self, text):
        words = text.split()
        return ' '.join(words[-2:]) if len(words) >= 2 else text

    def _convert_date(self, date_str):
        try:
            return datetime.strptime(date_str, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError(f"Format de date invalide : {date_str}. Utilisez le format DD/MM/YYYY.")

    def is_new_operation(self, row):
        """Vérifie si une ligne représente une nouvelle opération"""
        return row.get('Date', '').strip() != '' and row.get('Solde(XPF)', '').strip() != ''

    def is_total_line(self, row):
        return 'Total' in (row.get("Libellé de l'opération") or '')

    def _extract_partner_name(self, part):
        """Extrait le nom du partenaire à partir de la référence complète"""
        if not part:
            return None

        # Supprimer les préfixes spécifiques
        part = part.replace("VIREMENT RECUVRT SOC ", "").replace("VIREMENTS POLYNESIEVRT MP ", "")\
            .replace("SUR COMPTE DE TIERS", "").replace("VRT MARARA PAIEMENT", "")\
            .replace("REJET ", "").replace("VRT MP ", "").replace("VRT SOC ", "")\
            .replace("Numero TAHITI R", "")
        # Garder uniquement ce qui précède un chiffre
        part = re.split(r'\d', part)[0].strip()

        return part

    def _extract_ref(self, part):
        """Extrait la référence à partir de la référence complète"""
        if not part:
            return None

        # Supprimer les préfixes spécifiques
        part = part.replace("VIREMENT RECU", "").replace("VIREMENTS POLYNESIE", "")\
            .replace("SUR COMPTE DE TIERS", "").replace("VRT MARARA PAIEMENT", "VRT MP")\
            .replace("Numero TAHITI R", "N° TAHITI R")

        return part

    def _create_attachment(self, statement):
        """Crée une pièce jointe du fichier importé dans le chatter du relevé"""
        if not self.file_data:
            return
        
        # Créer la pièce jointe
        attachment = self.env['ir.attachment'].create({
            'name': statement.name,
            'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_ccp').id])],
            'datas': self.file_data,
            'res_model': 'account.bank.statement',
            'res_id': statement.id,
            'type': 'binary',
            'mimetype': 'text/csv',
        })
        
        # Poster un message dans le chatter avec la pièce jointe
        statement.message_post(
            body=f"Relevé CCP importé : {statement.name}.htm",
            attachment_ids=[attachment.id],
            subject=f"Relevé CCP importé : {statement.name}.htm",
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
                'name': f"{statement.name} (PDF)",
                'category_ids': [(6, 0, [self.env.ref('l10n_pf_gov_rch.attachment_cat_bank_ccp').id])],
                'datas': pdf_data,
                'res_model': 'account.bank.statement',
                'res_id': statement.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
            })

            # Poster un message dans le chatter avec la pièce jointe PDF
            statement.message_post(
                body=f"Relevé CCP généré : {statement.name}.pdf",
                attachment_ids=[pdf_attachment.id],
                subject=f"Relevé CCP généré : {statement.name}.pdf",
            )

            return pdf_attachment

        except Exception as e:
            # Log l'erreur sans interrompre le processus
            _logger.warning(f"Erreur lors de la création du PDF pour le relevé {statement.name}: {str(e)}")
            return None

    def action_bank_statement_import_ccpbq(self):
        try:
            file_content = base64.b64decode(self.file_data).decode('utf-8')
        except Exception as e:
            raise ValueError(
                "Erreur lors du décodage du fichier. Vérifiez que le fichier est au format attendu.") from e

        # Diviser le contenu en lignes et chercher la ligne d'en-tête
        lines = file_content.splitlines()
        header_line_index = None
        
        for i, line in enumerate(lines):
            # Debug: afficher chaque ligne pour diagnostiquer
            _logger.info(f"Ligne {i}: {repr(line)}")
            
            # Chercher la ligne qui contient les mots clés principaux
            line_lower = line.lower()
            if ('date' in line_lower and 'valeur' in line_lower and 
                ('libellé' in line_lower or 'libelle' in line_lower) and 
                ('opération' in line_lower or 'operation' in line_lower)):
                header_line_index = i
                _logger.info(f"En-tête trouvée à la ligne {i}")
                break
        
        if header_line_index is None:
            raise ValueError("Impossible de trouver la ligne d'en-tête dans le fichier CSV")
        
        # Prendre les lignes après l'en-tête
        data_lines = lines[header_line_index + 1:]
        
        # Nettoyer les lignes vides et reconstruire le CSV
        cleaned_lines = [lines[header_line_index]]  # Garder l'en-tête
        
        for line in data_lines:
            if line.strip() and not line.startswith(';;'):
                cleaned_lines.append(line)
        
        # Reconstruire le contenu CSV
        csv_content = '\n'.join(cleaned_lines)
        
        csv_reader = csv.DictReader(csv_content.splitlines(), delimiter=';')
        move_ids = []
        date = None

        def process_line(row):
            """Traite une ligne individuelle du relevé bancaire"""
            try:
                # Debug: Afficher le contenu de la ligne
                _logger.info(f"Traitement de la ligne : {row}")
                
                # Convertir la date
                date_line = self._convert_date(row['Date'])
                
                # Récupérer le libellé de l'opération
                ref = row.get("Libellé de l'opération", '').strip()
                if not ref:
                    ref = "Opération sans libellé"
                else:
                    # Normalise les caractères Unicode
                    ref = unicodedata.normalize('NFKC', ref)
                    # Remplace tous les caractères d'espacement par des espaces normaux
                    ref = re.sub(r'[\s\u00A0\u2000-\u200B\u2028\u2029\u202F\u205F\u3000]+', ' ', ref)
                    # Nettoyer les espaces multiples
                    ref = ' '.join(ref.split())

                # Calculer le montant (crédit - débit)
                credit_str = row.get('Crédit(XPF)', '').strip()
                debit_str = row.get('Débit(XPF)', '').strip()
                
                credit = 0
                if credit_str:
                    try:
                        credit = float(credit_str.replace(',', '.'))
                    except (ValueError, TypeError):
                        _logger.warning(f"Impossible de convertir le crédit : {credit_str}")
                
                debit = 0
                if debit_str:
                    try:
                        debit = float(debit_str.replace(',', '.'))
                    except (ValueError, TypeError):
                        _logger.warning(f"Impossible de convertir le débit : {debit_str}")
                
                amount = credit - debit
                
                # Récupérer le solde
                balance_str = row.get('Solde(XPF)', '').strip()
                balance = 0
                if balance_str:
                    try:
                        balance = float(balance_str.replace(',', '.'))
                    except (ValueError, TypeError):
                        _logger.warning(f"Impossible de convertir le solde : {balance_str}")
                
                # Debug: Afficher les valeurs trouvées
                _logger.info(f"Libellé trouvé : {ref}")
                _logger.info(f"Crédit : {credit}, Débit : {debit}, Montant : {amount}")
                _logger.info(f"Solde : {balance}")

                move_ids.append({
                    'date': date_line,
                    'ref': ref,
                    'payment_ref': ref,
                    'credit': amount,
                    'balance': balance,
                })
                return date_line
            except Exception as e:
                _logger.warning(f"Erreur lors du traitement de la ligne : {row}\nErreur : {e}")
                return None

        # Parcourir toutes les lignes (maintenant chaque ligne est une opération complète)
        for row in csv_reader:
            # Vérifier si c'est une ligne de total (fin du fichier)
            if self.is_total_line(row):
                break

            # Vérifier si la ligne contient une date (opération valide)
            if row.get('Date', '').strip():
                processed_date = process_line(row)
                if processed_date:
                    date = processed_date

        # Création ou récupération du journal bancaire
        journal_code = 'CCPBQ'
        journal_name = 'CCP (Virements)'
        journal = self.env['account.journal'].search([('code', '=', journal_code)], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': journal_name,
                'code': journal_code,
                'type': 'bank',
            })

        # Création ou récupération du relevé
        statement = self.env['account.bank.statement'].search([
            ('journal_id', '=', journal.id),
            ('state', '!=', 'confirm'),
            ('date', '=', date)
        ], limit=1)
        if not statement:
            statement = self.env['account.bank.statement'].create({
                'journal_id': journal.id,
                'date': date,
                'name': f"Relevé Marara Paiement {date.strftime('%Y%m%d')}",  # Correction du bug ici
            })

        # Créer les lignes de relevé bancaire
        for line in move_ids:
            partner_name = self._extract_partner_name(line['ref'])
            ref = self._extract_ref(line['ref'])
            partner = None
            if partner_name:
                partner = self.env['res.partner'].search([
                    ('name', '=', partner_name)
                ], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': partner_name,
                    })

            self.env['account.bank.statement.line'].create({
                'statement_id': statement.id,
                'date': line['date'],
                'partner_id': partner.id if partner else False,
                'ref': ref,
                'payment_ref': ref,
                'amount': line['credit'],
                'journal_id': journal.id,
            })

            # Créer un paiement si c'est un crédit
            if line['credit'] > 0:
                self.env['account.payment'].create({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': partner.id if partner else False,
                    'amount': line['credit'],
                    'date': line['date'],
                    'journal_id': journal.id,
                    'payment_method_id': self.env.ref('account.account_payment_method_manual_in').id,
                    'ref': ref,
                })

        # Ajouter les fichiers en pièce jointe dans le chatter
        self._create_attachment(statement)  # CSV existant
        self._create_pdf_attachment(statement)  # PDF nouveau

        return {
            'type': 'ir.actions.act_window',
            'name': 'Importation réussie des bordereaux de recettes CCP',
            'res_model': 'account.bank.statement',
            'view_mode': 'form',
            'res_id': statement.id,
            'target': 'current',
        }

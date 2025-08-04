from odoo import models, fields
from odoo.exceptions import UserError
import pandas as pd
import base64
import io
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


def count_integers_leq_12(s):
    """Fonction pour compter les entiers inférieurs ou égaux à 12"""
    if not s or s == '':
        return 0
    numbers = s.split(', ')
    count = sum(1 for num in numbers
                if num.strip() and num.strip().isdigit()
                and int(num.strip()) <= 12)
    return count


class BookingImportWizard(models.TransientModel):
    _name = 'booking.import.wizard'
    _description = 'Assistant d\'importation de fichier Booking.com'

    file_data = fields.Binary(string='Fichier Excel', required=True)
    file_name = fields.Char(string='Nom du fichier')
    preview_data = fields.Text(string='Aperçu des données', readonly=True)
    state = fields.Selection([
        ('upload', 'Upload du fichier'),
        ('preview', 'Aperçu des données'),
        ('confirm', 'Confirmation')
    ], default='upload', string='Étape')
    
    # Champs pour l'aperçu
    total_records = fields.Integer(string='Nombre total d\'enregistrements', readonly=True)
    valid_records = fields.Integer(string='Enregistrements valides', readonly=True)
    
    def action_preview(self):
        """Prévisualise les données du fichier avant import"""
        self.ensure_one()
        
        if not self.file_data:
            raise UserError("Veuillez sélectionner un fichier à importer.")
        
        try:
            # Lire le fichier Excel
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')
            
            self.total_records = len(df)
            
            # Filtrer les enregistrements valides
            valid_df = df[df['Statut'].str.contains("ok", na=False)]
            self.valid_records = len(valid_df)
            
            # Créer un aperçu des données
            preview_lines = []
            for idx, row in valid_df.head(10).iterrows():
                customer_name = row['Nom du client'] or self._inverse_name_first_name(row.get("Réservé par", ""))
                housing_type = row.get("Type d'hébergement", "")
                arrival_date = row.get('Arrivée', "")
                duration = row.get('Durée (nuits)', 0)
                pax = row.get('Personnes', 0)
                
                preview_lines.append(f"• {customer_name} - {housing_type} - {arrival_date} ({duration} nuits, {pax} pers.)")
            
            if len(valid_df) > 10:
                preview_lines.append(f"... et {len(valid_df) - 10} autres enregistrements")
            
            self.preview_data = "\n".join(preview_lines)
            self.state = 'preview'
            
        except Exception as e:
            _logger.error(f"Erreur lors de la prévisualisation : {e}")
            raise UserError(f"Erreur lors de la lecture du fichier : {str(e)}")
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_import(self):
        """Effectue l'importation des données"""
        self.ensure_one()
        
        if not self.file_data:
            raise UserError("Aucun fichier à importer.")
        
        try:
            # Lire le fichier Excel
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')
            df = df[df['Statut'].str.contains("ok", na=False)]
            df['Arrivée'] = pd.to_datetime(df['Arrivée'], errors='coerce')
            
            # Créer/récupérer le partenaire Booking.com
            supplier_id = self._get_or_create_booking_partner()
            
            # Regrouper les lignes par (year, month, property_type_id)
            grouped_lines = self._group_lines_by_period(df)
            
            # Créer les enregistrements d'importation
            created_imports = self._create_import_records(grouped_lines)
            
            # Supprimer les enregistrements invalides
            self._cleanup_invalid_records()
            
            # Créer les factures
            # for import_record in created_imports:
            #     import_record.municipality_invoice()
                # import_record.concierge_invoice()
                # import_record.booking_invoice()
            
            self.state = 'confirm'
            
            # Retourner la vue des imports créés
            return self._show_created_imports(created_imports)
            
        except Exception as e:
            _logger.error(f"Erreur lors de l'importation : {e}")
            raise UserError(f"Erreur lors de l'importation : {str(e)}")
    
    def _inverse_name_first_name(self, texte):
        """Inverse nom, prénom en prénom nom"""
        if ',' in texte:
            name, first_name = texte.split(',', 1)
            return first_name.strip() + ' ' + name.strip()
        return texte
    
    def _get_or_create_booking_partner(self):
        """Récupère ou crée le partenaire Booking.com"""
        supplier_id = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)
        if not supplier_id:
            supplier_id = self.env['res.partner'].create({
                'name': 'Booking.com',
                'street': 'Herengracht 597',
                'city': 'Amsterdam',
                'zip': '1017 CE',
                'country_id': self.env['res.country'].search([('code', '=', 'NL')]).id,
                'phone': '+31 20 201 8800',
                'email': 'customer.service@booking.com',
                'is_company': True,
                'supplier_rank': 1,
            })
        return supplier_id
    
    def _group_lines_by_period(self, df):
        """Regroupe les lignes par période (année, mois, type de propriété)"""
        grouped_lines = defaultdict(list)
        
        for _, row in df.iterrows():
            customer_name = row['Nom du client'] or self._inverse_name_first_name(row.get("Réservé par", ""))
            
            arrival_date = pd.to_datetime(row['Arrivée'], errors='coerce')
            if pd.isnull(arrival_date):
                continue
            
            year = arrival_date.year
            month = arrival_date.month
            
            # Créer/récupérer le client
            partner = self._get_or_create_partner(row, customer_name)
            
            # Créer/récupérer le type d'hébergement
            property_type = self._get_or_create_property_type(row)
            
            # Ajouter la ligne au groupe
            key = (year, month, property_type.id)
            grouped_lines[key].append((0, 0, {
                'partner_id': partner.id,
                'booker_id': partner.id,
                'arrival_date': arrival_date,
                'duration_nights': row.get('Durée (nuits)', 0),
                'children': count_integers_leq_12(str(row.get('Âges des enfants', ''))),
                'property_type_id': property_type.id,
                'payment_status': row.get('Statut du paiement', ''),
                'status': row.get('Statut', ''),
                'pax_nb': row.get('Personnes', 0),
                'rate': float(str(row.get('Tarif', '0')).replace(' XPF', '').replace(',', '') or 0),
                'commission_amount': float(str(row.get('Montant de la commission', '0'))
                                         .replace(' XPF', '').replace(',', '').strip() or 0),
            }))
        
        return grouped_lines
    
    def _get_or_create_partner(self, row, customer_name):
        """Récupère ou crée un partenaire"""
        partner = self.env['res.partner'].search([('name', '=', customer_name)], limit=1)
        if not partner:
            country_id = False
            booker_country = row.get('Booker country', '')
            if booker_country:
                country = self.env['res.country'].search([('name', '=', booker_country)], limit=1)
                country_id = country.id if country else False
            
            partner = self.env['res.partner'].create({
                'name': customer_name,
                'phone': row.get('Numéro de téléphone', ''),
                'country_id': country_id,
                'company_id': self.env.user.company_id.id
            })
        return partner
    
    def _get_or_create_property_type(self, row):
        """Récupère ou crée un type de propriété"""
        housing_type = row.get("Type d'hébergement", "")
        property_type = self.env['product.template'].search([('name', '=', housing_type)], limit=1)
        if not property_type:
            property_type = self.env['product.template'].create({
                'name': housing_type,
                'purchase_ok': False,
                'company_id': self.env.user.company_id.id
            })
        return property_type
    
    def _create_import_records(self, grouped_lines):
        """Crée les enregistrements d'importation"""
        created_imports = []
        for (year, month, property_type_id), lines in grouped_lines.items():
            property_type = self.env['product.template'].browse(property_type_id)
            
            # Chercher un enregistrement existant
            import_record = self.env['booking.import'].search([
                ('year', '=', year),
                ('month', '=', str(month)),
                ('property_type_id', '=', property_type_id)
            ], limit=1)
            
            if not import_record:
                import_record = self.env['booking.import'].create({
                    'year': year,
                    'month': str(month),
                    'property_type_id': property_type_id,
                    'import_date': fields.Datetime.now(),
                    'company_id': self.env.company.id,
                    'line_ids': lines
                })
            else:
                # Ajouter les nouvelles lignes aux existantes
                import_record.write({'line_ids': lines})
            
            created_imports.append(import_record)
        
        return created_imports
    
    def _cleanup_invalid_records(self):
        """Supprime les enregistrements invalides"""
        invalid_records = self.env['booking.import'].search([('name', '=', '0-00 False')])
        if invalid_records:
            invalid_records.unlink()
    
    def _show_created_imports(self, created_imports):
        """Affiche les imports créés"""
        if len(created_imports) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Import créé',
                'res_model': 'booking.import',
                'view_mode': 'form',
                'res_id': created_imports[0].id,
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Imports créés',
                'res_model': 'booking.import',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', [imp.id for imp in created_imports])],
                'target': 'current',
            }
    
    def action_cancel(self):
        """Annule le wizard"""
        return {'type': 'ir.actions.act_window_close'}

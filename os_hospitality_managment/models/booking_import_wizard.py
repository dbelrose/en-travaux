# -*- coding: utf-8 -*-
from odoo import models, fields
from odoo.exceptions import UserError
import pandas as pd
import base64
import io
import logging

_logger = logging.getLogger(__name__)


def count_integers_leq_12(s):
    """Compte les entiers <= 12 dans une chaîne séparée par des virgules"""
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

    import_id = fields.Many2one('booking.import', string='Import', required=True)
    file_data = fields.Binary(string='Fichier Excel/CSV', required=True)
    file_name = fields.Char(string='Nom du fichier')

    # État du wizard
    state = fields.Selection([
        ('upload', 'Upload du fichier'),
        ('preview', 'Aperçu des données'),
        ('import', 'Import terminé')
    ], default='upload', string='Étape')

    # Données de prévisualisation
    preview_data = fields.Text(string='Aperçu des données', readonly=True)
    total_records = fields.Integer(string='Total enregistrements', readonly=True)
    valid_records = fields.Integer(string='Enregistrements valides', readonly=True)
    duplicate_records = fields.Integer(string='Doublons détectés', readonly=True)

    # Options d'import
    skip_duplicates = fields.Boolean(string='Ignorer les doublons', default=True)
    update_existing = fields.Boolean(string='Mettre à jour les existants', default=False)

    def _inverse_name_first_name(self, texte):
        """Inverse nom, prénom en prénom nom"""
        if ',' in texte:
            name, first_name = texte.split(',', 1)
            return first_name.strip() + ' ' + name.strip()
        return texte

    def action_preview(self):
        """Prévisualise les données avant import"""
        self.ensure_one()

        if not self.file_data:
            raise UserError("Veuillez sélectionner un fichier.")

        try:
            # Lire le fichier
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')

            self.total_records = len(df)

            # Filtrer les enregistrements valides (statut OK)
            valid_df = df[df['Statut'].str.contains("ok", na=False)]
            self.valid_records = len(valid_df)

            # Détecter les doublons potentiels
            duplicates = 0
            preview_lines = []

            for idx, row in valid_df.head(10).iterrows():
                customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(
                    row.get("Réservé par", ""))
                housing_type = row.get("Type d'hébergement", "")
                arrival_date = row.get('Arrivée', "")
                duration = row.get('Durée (nuits)', 0)
                pax = row.get('Personnes', 0)

                preview_lines.append(
                    f"• {customer_name} - {housing_type} - {arrival_date} ({duration} nuits, {pax} pers.)")

                # Vérifier les doublons
                if self._check_duplicate(row):
                    duplicates += 1

            if len(valid_df) > 10:
                preview_lines.append(f"... et {len(valid_df) - 10} autres enregistrements")

            self.preview_data = "\n".join(preview_lines)
            self.duplicate_records = duplicates
            self.state = 'preview'

        except Exception as e:
            _logger.error(f"Erreur lors de la prévisualisation : {e}")
            raise UserError(f"Erreur lors de la lecture du fichier : {str(e)}")

        return self._return_wizard()

    def _check_duplicate(self, row):
        """Vérifie si l'enregistrement est un doublon"""
        try:
            customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(row.get("Réservé par", ""))
            arrival_date = pd.to_datetime(row.get('Arrivée'), errors='coerce')
            housing_type = row.get("Type d'hébergement", "")
            duration = row.get('Durée (nuits)', 0)

            if pd.isnull(arrival_date):
                return False

            # Rechercher dans les réservations existantes
            existing = self.env['booking.import.line'].search([
                ('partner_id.name', '=', customer_name),
                ('arrival_date', '=', arrival_date.date()),
                ('property_type_id.name', '=', housing_type),
                ('duration_nights', '=', duration),
                ('status', '!=', 'cancelled'),
            ], limit=1)

            return bool(existing)
        except:
            return False

    def action_import(self):
        """Effectue l'import des données"""
        self.ensure_one()

        if not self.file_data:
            raise UserError("Aucun fichier à importer.")

        try:
            # Lire le fichier
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')
            df = df[df['Statut'].str.contains("ok", na=False)]
            df['Arrivée'] = pd.to_datetime(df['Arrivée'], errors='coerce')
            df['Départ'] = pd.to_datetime(df['Départ'], errors='coerce')

            # Statistiques d'import
            imported_count = 0
            updated_count = 0
            skipped_count = 0

            for _, row in df.iterrows():
                try:
                    result = self._process_reservation_row(row)
                    if result == 'imported':
                        imported_count += 1
                    elif result == 'updated':
                        updated_count += 1
                    elif result == 'skipped':
                        skipped_count += 1
                except Exception as e:
                    _logger.error(f"Erreur lors du traitement de la ligne : {e}")
                    continue

            # Mettre à jour l'import
            self.import_id.write({
                'state': 'imported',
                'file_name': self.file_name,
                'notes': f"Import terminé : {imported_count} nouvelles, {updated_count} mises à jour, {skipped_count} ignorées"
            })

            self.state = 'import'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import terminé',
                    'message': f'{imported_count} réservations importées, {updated_count} mises à jour, {skipped_count} ignorées.',
                    'type': 'success',
                }
            }

        except Exception as e:
            _logger.error(f"Erreur lors de l'import : {e}")
            raise UserError(f"Erreur lors de l'import : {str(e)}")

    def _process_reservation_row(self, row):
        """Traite une ligne de réservation"""
        customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(row.get("Réservé par", ""))
        housing_type = row.get("Type d'hébergement", "")
        arrival_date = row.get('Arrivée')
        departure_date = row.get('Départ')
        reservation_date = row.get('Réservé le')

        if pd.isnull(arrival_date):
            return 'skipped'

        # Créer/récupérer le client
        partner = self._get_or_create_partner(row, customer_name)

        # Créer/récupérer le type d'hébergement
        property_type = self._get_or_create_property_type(housing_type)

        # Générer un ID externe unique
        _logger.info(f"customer_name : {customer_name}")
        _logger.info(f"housing_type : {housing_type}")
        external_id = f"booking_{arrival_date.strftime('%Y%m%d')}_{customer_name.replace(' ', '_')}_{housing_type.replace(' ', '_')}"

        # Vérifier les doublons
        existing = self.env['booking.import.line'].search([
            ('external_id', '=', external_id),
            ('property_type_id', '=', property_type.id),
        ], limit=1)

        line_vals = {
            'import_id': self.import_id.id,
            'external_id': external_id,
            'booking_reference': row.get('Référence', ''),
            'partner_id': partner.id,
            'booker_id': partner.id,
            'property_type_id': property_type.id,
            'arrival_date': arrival_date.date(),
            'departure_date': departure_date.date(),
            'reservation_date': reservation_date.date(),
            'duration_nights': int(row.get('Durée (nuits)', 1)),
            'pax_nb': int(row.get('Personnes', 1)),
            'children': count_integers_leq_12(str(row.get('Âges des enfants', ''))),
            'payment_status': self._map_payment_status(row.get('Statut du paiement', '')),
            'status': 'ok',
            'rate': self._parse_amount(row.get('Tarif', '0')),
            'commission_amount': self._parse_amount(row.get('Montant de la commission', '0')),
            'source': 'booking',
        }

        if existing:
            if self.skip_duplicates:
                return 'skipped'
            elif self.update_existing:
                existing.write(line_vals)
                return 'updated'
            else:
                return 'skipped'
        else:
            self.env['booking.import.line'].create(line_vals)
            return 'imported'

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
                'company_id': self.env.user.company_id.id,
                'customer_rank': 1,
                'category_id': [
                    (6, 0, self.env.ref('os_hospitality_managment.res_partner_category_plateforme_booking').ids)]
            })
        return partner

    def _get_or_create_property_type(self, housing_type):
        """Récupère ou crée un type de propriété"""
        property_type = self.env['product.template'].search([('name', '=', housing_type)], limit=1)
        if not property_type:
            property_type = self.env['product.template'].create({
                'name': housing_type,
                'purchase_ok': False,
                'company_id': self.env.user.company_id.id
            })
        return property_type

    def _map_payment_status(self, status):
        """Mappe le statut de paiement"""
        mapping = {
            'Entièrement payée': 'paid',
            'Partiellement payée': 'partial',
            'Non payée': 'unpaid',
            'Remboursée': 'refunded',
        }
        return mapping.get(status, 'paid')

    def _parse_amount(self, amount_str):
        """Convertit un montant en float"""
        if not amount_str:
            return 0.0
        try:
            # Nettoyer la chaîne (enlever XPF, espaces, virgules)
            clean_str = str(amount_str).replace(' XPF', '').replace(',', '').replace(' ', '').strip()
            return float(clean_str) if clean_str else 0.0
        except:
            return 0.0

    def _return_wizard(self):
        """Retourne la vue du wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_cancel(self):
        """Annule le wizard"""
        return {'type': 'ir.actions.act_window_close'}

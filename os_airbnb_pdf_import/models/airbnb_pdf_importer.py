import re
import logging
from datetime import datetime
from odoo import models, fields, _
from odoo.exceptions import UserError
import PyPDF2
import io
import base64

_logger = logging.getLogger(__name__)


class AirbnbPdfImporter(models.TransientModel):
    _name = 'airbnb.pdf.importer'
    _description = 'Importateur PDF Airbnb'

    pdf_file = fields.Binary(string='Fichier PDF', required=True)
    pdf_filename = fields.Char(string='Nom du fichier')
    import_id = fields.Many2one('booking.import', string='Import', required=True)

    def _extract_text_from_pdf(self, pdf_data):
        """Extrait le texte du PDF"""
        try:
            pdf_bytes = base64.b64decode(pdf_data)
            pdf_stream = io.BytesIO(pdf_bytes)

            # Support pour différentes versions de PyPDF2
            try:
                # PyPDF2 >= 3.0
                pdf_reader = PyPDF2.PdfReader(pdf_stream)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
            except AttributeError:
                # PyPDF2 < 3.0 (ancienne API)
                pdf_reader = PyPDF2.PdfFileReader(pdf_stream)
                text = ""
                for page_num in range(pdf_reader.numPages):
                    page = pdf_reader.getPage(page_num)
                    text += page.extractText()

            return text
        except Exception as e:
            _logger.error(f"Erreur lors de l'extraction du PDF: {e}")
            raise UserError(_("Impossible d'extraire le texte du PDF: %s") % str(e))

    def _parse_airbnb_data(self, text):
        """Parse les données du PDF Airbnb"""
        data = {}

        try:
            # Extraction du nom du client
            name_pattern = r"Ancien voyageur\s*\n\s*([^\n]+)"
            name_match = re.search(name_pattern, text)
            if name_match:
                full_name = name_match.group(1).strip()
                name_parts = full_name.split()
                data['first_name'] = name_parts[0] if name_parts else ''
                data['last_name'] = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

            # Extraction du téléphone
            phone_pattern = r"Téléphone\s*:\s*([^\n]+)"
            phone_match = re.search(phone_pattern, text)
            if phone_match:
                data['phone'] = phone_match.group(1).strip()

            # Extraction de la ville et pays
            location_pattern = r"Habite à\s*([^,\n]+)(?:,\s*([^\n]+))?"
            location_match = re.search(location_pattern, text)
            if location_match:
                data['city'] = location_match.group(1).strip()
                data['country'] = location_match.group(2).strip() if location_match.group(2) else 'États-Unis'

            # Extraction de la langue
            language_pattern = r"Langues\s*:\s*([^\n]+)"
            language_match = re.search(language_pattern, text)
            if language_match:
                lang_text = language_match.group(1).strip()
                # Mapping des langues
                lang_mapping = {
                    'Anglais': 'en_US',
                    'Français': 'fr_FR',
                    'English': 'en_US',
                    'French': 'fr_FR'
                }
                data['language'] = lang_mapping.get(lang_text, 'en_US')

            # Extraction du type de logement
            property_pattern = r"([^\n]*chambres?[^\n]*)"
            property_match = re.search(property_pattern, text, re.IGNORECASE)
            if property_match:
                data['property_type'] = property_match.group(1).strip()

            # Extraction des dates
            date_pattern = r"(\d{1,2})\s+(\w+)\.?\s*–\s*(\d{1,2})\s+(\w+)\s*\((\d+)\s+nuits?\)"
            date_match = re.search(date_pattern, text)
            if date_match:
                start_day = int(date_match.group(1))
                start_month = self._parse_french_month(date_match.group(2))
                end_day = int(date_match.group(3))
                end_month = self._parse_french_month(date_match.group(4))
                nights = int(date_match.group(5))

                # Assumons année 2025 (peut être ajusté selon le contexte)
                current_year = 2025
                data['arrival_date'] = datetime(current_year, start_month, start_day).date()
                data['departure_date'] = datetime(current_year, end_month, end_day).date()
                data['duration_nights'] = nights

            # Extraction du nombre de voyageurs
            travelers_pattern = r"(\d+)\s+voyageurs?"
            travelers_match = re.search(travelers_pattern, text)
            if travelers_match:
                data['pax_nb'] = int(travelers_match.group(1))

            # Extraction des adultes (si spécifié)
            adults_pattern = r"(\d+)\s+adultes?"
            adults_match = re.search(adults_pattern, text)
            if adults_match:
                data['adults'] = int(adults_match.group(1))
            else:
                data['adults'] = data.get('pax_nb', 1)  # Par défaut, tous sont adultes

            # Extraction du code de confirmation
            confirmation_pattern = r"Code de confirmation\s*\n\s*([A-Z0-9]+)"
            confirmation_match = re.search(confirmation_pattern, text)
            if confirmation_match:
                data['booking_reference'] = confirmation_match.group(1).strip()

            # Extraction du montant total
            total_pattern = r"Total \(EUR\)\s*([0-9.,]+)\s*€"
            total_match = re.search(total_pattern, text)
            if total_match:
                total_str = total_match.group(1).replace(',', '.')
                data['rate'] = float(total_str)

            # Extraction du versement hôte (commission)
            host_payment_pattern = r"Total \(EUR\)\s*([0-9.,]+)\s*€"
            # Trouver tous les montants totaux
            all_totals = re.findall(r"Total \(EUR\)\s*([0-9.,]+)\s*€", text)
            if len(all_totals) >= 2:
                guest_total = float(all_totals[0].replace(',', '.'))
                host_total = float(all_totals[1].replace(',', '.'))
                data['commission_amount'] = guest_total - host_total

            # Extraction de la date de réservation
            booking_date_pattern = r"Date de réservation\s*\n\s*\w+\.\s*(\d{1,2})\s+(\w+)\.\s*(\d{4})"
            booking_date_match = re.search(booking_date_pattern, text)
            if booking_date_match:
                day = int(booking_date_match.group(1))
                month = self._parse_french_month(booking_date_match.group(2))
                year = int(booking_date_match.group(3))
                data['reservation_date'] = datetime(year, month, day).date()

            return data

        except Exception as e:
            _logger.error(f"Erreur lors du parsing des données Airbnb: {e}")
            raise UserError(_("Erreur lors de l'analyse du PDF: %s") % str(e))

    def _parse_french_month(self, month_str):
        """Convertit les mois français en numéros"""
        months = {
            'janv': 1, 'janvier': 1,
            'févr': 2, 'février': 2,
            'mars': 3,
            'avr': 4, 'avril': 4,
            'mai': 5,
            'juin': 6,
            'juil': 7, 'juillet': 7,
            'août': 8,
            'sept': 9, 'septembre': 9,
            'oct': 10, 'octobre': 10,
            'nov': 11, 'novembre': 11,
            'déc': 12, 'décembre': 12
        }
        return months.get(month_str.lower(), 1)

    def _create_partner(self, data):
        """Crée ou trouve un partner"""
        Partner = self.env['res.partner']

        # Recherche d'un partner existant
        domain = []
        if data.get('phone'):
            domain.append(('phone', '=', data['phone']))

        if data.get('first_name') and data.get('last_name'):
            name = f"{data['first_name']} {data['last_name']}"
            if not domain:  # Si pas de téléphone, chercher par nom
                domain.append(('name', '=', name))
        else:
            name = data.get('first_name', 'Client Airbnb')

        partner = None
        if domain:
            partner = Partner.search(domain, limit=1)

        if not partner:
            # Trouver le pays
            country = None
            if data.get('country'):
                country = self.env['res.country'].search([
                    '|',
                    ('name', 'ilike', data['country']),
                    ('code', '=', self._get_country_code(data['country']))
                ], limit=1)

            partner_vals = {
                'name': name,
                'phone': data.get('phone', ''),
                'city': data.get('city', ''),
                'country_id': country.id if country else False,
                'lang': data.get('language', 'en_US'),
                'is_company': False,
                'customer_rank': 1,
            }
            partner = Partner.create(partner_vals)

        return partner

    def _get_country_code(self, country_name):
        """Retourne le code pays"""
        country_mapping = {
            'États-Unis': 'US',
            'Virginie': 'US',  # État des États-Unis
            'France': 'FR',
            'Royaume-Uni': 'GB',
            'Canada': 'CA',
        }
        return country_mapping.get(country_name, 'US')

    def _create_booking_line(self, data, partner):
        """Crée une ligne de réservation"""
        BookingLine = self.env['booking.import.line']

        # Trouver ou créer le type de propriété
        property_type = self._get_or_create_property_type(data.get('property_type', 'Logement Airbnb'))

        # Convertir le montant EUR en XPF (taux approximatif)
        # 1 EUR ≈ 119.33 XPF (à ajuster selon le taux en vigueur)
        eur_to_xpf_rate = 119.33
        rate_xpf = data.get('rate', 0) * eur_to_xpf_rate
        commission_xpf = data.get('commission_amount', 0) * eur_to_xpf_rate

        booking_vals = {
            'import_id': self.import_id.id,
            'partner_id': partner.id,
            'booker_id': partner.id,  # Même personne pour Airbnb
            'property_type_id': property_type.id,
            'arrival_date': data.get('arrival_date'),
            'departure_date': data.get('departure_date'),
            'reservation_date': data.get('reservation_date', fields.Date.today()),
            'duration_nights': data.get('duration_nights', 1),
            'pax_nb': data.get('pax_nb', 1),
            'adults': data.get('adults', data.get('pax_nb', 1)),
            'children': max(0, data.get('pax_nb', 1) - data.get('adults', 1)),
            'booking_reference': data.get('booking_reference', ''),
            'booking_id': data.get('booking_reference', ''),  # Même valeur pour Airbnb
            'payment_status': 'Entièrement payée',  # Par défaut pour Airbnb
            'status': 'ok',
            'rate': rate_xpf,
            'commission_amount': commission_xpf,
        }

        booking_line = BookingLine.create(booking_vals)
        return booking_line

    def _get_or_create_property_type(self, property_description):
        """Trouve ou crée le type de propriété"""
        ProductTemplate = self.env['product.template']

        # Nettoyer la description
        clean_description = property_description.strip()

        # Rechercher un produit existant
        product = ProductTemplate.search([
            ('name', 'ilike', clean_description)
        ], limit=1)

        if not product:
            # Créer un nouveau type de propriété
            product_vals = {
                'name': clean_description,
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'categ_id': self._get_accommodation_category().id,
            }
            product = ProductTemplate.create(product_vals)

        return product

    def _get_accommodation_category(self):
        """Retourne ou crée la catégorie hébergement"""
        category = self.env['product.category'].search([
            ('name', '=', 'Hébergements')
        ], limit=1)

        if not category:
            category = self.env['product.category'].create({
                'name': 'Hébergements'
            })

        return category

    def import_airbnb_pdf(self):
        """Méthode principale d'import"""
        if not self.pdf_file:
            raise UserError(_("Veuillez sélectionner un fichier PDF."))

        try:
            # Extraction du texte
            text = self._extract_text_from_pdf(self.pdf_file)

            # Parsing des données
            data = self._parse_airbnb_data(text)

            # Création du partner
            partner = self._create_partner(data)

            # Création de la ligne de réservation
            booking_line = self._create_booking_line(data, partner)

            return {
                'type': 'ir.actions.act_window',
                'name': _('Réservation importée'),
                'view_mode': 'form',
                'res_model': 'booking.import.line',
                'res_id': booking_line.id,
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Erreur lors de l'import Airbnb: {e}")
            raise UserError(_("Erreur lors de l'import: %s") % str(e))


class BookingImport(models.Model):
    _name = 'booking.import'
    _description = 'Import de réservations'

    name = fields.Char(string='Nom', required=True)
    company_id = fields.Many2one('res.company', string='Société',
                                 default=lambda self: self.env.company)
    def action_import_airbnb_pdf(self):
        """Action pour ouvrir l'assistant d'import PDF"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importer PDF Airbnb'),
            'view_mode': 'form',
            'res_model': 'airbnb.pdf.importer',
            'target': 'new',
            'context': {'default_import_id': self.id}
        }

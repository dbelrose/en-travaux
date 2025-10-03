from datetime import datetime, date
from odoo import models, fields, _
from odoo.exceptions import UserError

import re
import logging
import PyPDF2
import io
import base64
import fitz  # PyMuPDF

_logger = logging.getLogger(__name__)


class AirbnbPdfImporter(models.TransientModel):
    _name = 'airbnb.pdf.importer'
    _description = 'Importateur PDF Airbnb'

    pdf_file = fields.Binary(string='Fichier PDF', required=True)
    file_name = fields.Char(string='Nom du fichier')
    import_id = fields.Many2one('booking.import', string='Import', required=True)

    def _extract_phone_from_pdf_annotations_fitz(self, pdf_b64):
        """
        Retourne (raw, normalized) depuis la 1re occurrence 'tel:' trouvée
        dans les annotations de lien du PDF. Sinon (None, None).
        """
        if not pdf_b64:
            return None, None

        pdf_bytes = base64.b64decode(pdf_b64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            for page in doc:
                for ln in page.get_links():  # -> dict avec 'uri' + 'from' (rect)
                    uri = ln.get("uri")
                    if uri and uri.lower().startswith("tel:"):
                        raw = uri[4:].strip()  # ce que l’auteur a mis après tel:
                        # Normalisation : on conserve un + initial et uniquement des chiffres
                        if raw.startswith('+'):
                            normalized = '+' + re.sub(r'\D', '', raw[1:])
                        else:
                            normalized = re.sub(r'\D', '', raw)
                        return raw, normalized
            return None, None
        finally:
            doc.close()

    def _extract_first_uri_from_first_page(self, pdf_b64):
        """
        Retourne la première URI trouvée sur la page 1, ou None.
        """
        if not pdf_b64:
            return None

        pdf_bytes = base64.b64decode(pdf_b64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if len(doc) == 0:
                return None
            page = doc[0]
            for link in page.get_links():
                uri = link.get("uri")
                if uri:
                    return uri  # on prend la première trouvée
            return None
        finally:
            doc.close()

    def _extract_avatar_base64_from_first_page(self, pdf_b64, inflate_pt=6.0, dpi=144):
        """
        pdf_b64 : str (Base64 Odoo, ex. record.pdf_file)
        Retourne : str Base64 (prête pour image_1920) ou None
        """
        if not pdf_b64:
            return None

        pdf_bytes = base64.b64decode(pdf_b64)
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            if len(doc) == 0:
                return None
            page = doc[0]

            # 1) Si le PDF contient un lien Airbnb sur l’avatar, on s’aligne dessus
            try:
                links = page.get_links()  # chaque dict contient 'from' (Rect) et 'uri'
            except Exception:
                links = []

            for link in links:
                uri = (link.get("uri") or "").lower()
                if "airbnb." in uri and "/users/show/" in uri:
                    r = fitz.Rect(link["from"])
                    # 1) si 'inflated' existe (versions récentes) : l'utiliser
                    if hasattr(r, "inflated"):
                        link_rect = r.inflated(inflate_pt, inflate_pt)
                    # 2) sinon si 'inflate' existe (implémentations où l'opération est in-place)
                    elif hasattr(r, "inflate"):
                        r.inflate(inflate_pt, inflate_pt)  # modifie r en place
                        link_rect = r
                    # 3) sinon : élargissement manuel (compatible partout)
                    else:
                        link_rect = fitz.Rect(r.x0 - inflate_pt, r.y0 - inflate_pt, r.x1 + inflate_pt,
                                              r.y1 + inflate_pt)

                    # a) images "inline" via get_text("dict") -> blocks type==1 (avec bytes)
                    try:
                        blocks = page.get_text("dict")["blocks"]
                    except Exception:
                        blocks = []
                    for b in blocks:
                        if b.get("type") == 1 and "image" in b and "bbox" in b:
                            bbox = fitz.Rect(b["bbox"])
                            if bbox.intersects(link_rect):
                                return base64.b64encode(b["image"]).decode("ascii")

                    # b) fallback: images avec xref via get_image_info(xrefs=True)
                    try:
                        infos = page.get_image_info(xrefs=True)
                    except Exception:
                        infos = []
                    for im in infos:
                        bbox = fitz.Rect(im.get("bbox", (0, 0, 0, 0)))
                        if bbox.intersects(link_rect) and im.get("xref"):
                            base = doc.extract_image(im["xref"])
                            return base64.b64encode(base["image"]).decode("ascii")

                    # c) dernier recours: rasteriser la zone du lien
                    pix = page.get_pixmap(clip=link_rect, dpi=dpi)
                    return base64.b64encode(pix.tobytes("png")).decode("ascii")

            # 2) Pas de lien détecté : prendre la **plus grande image** de la page
            try:
                blocks = page.get_text("dict")["blocks"]
            except Exception:
                blocks = []

            img_blocks = [b for b in blocks if b.get("type") == 1 and "image" in b and "bbox" in b]
            if img_blocks:
                img_blocks.sort(key=lambda b: fitz.Rect(b["bbox"]).get_area(), reverse=True)
                return base64.b64encode(img_blocks[0]["image"]).decode("ascii")

            # 3) Dernier fallback: première image signalée par get_image_info
            try:
                infos = page.get_image_info(xrefs=True)
            except Exception:
                infos = []
            if infos:
                base = doc.extract_image(infos[0]["xref"])
                return base64.b64encode(base["image"]).decode("ascii")

            # return None
        finally:
            doc.close()

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
            data['origin'] = 'airbnb'  # Origine de la réservation
            data['import_type'] = 'pdf'

            # Extraction du nom du client
            name_pattern = r"Ancien voyageur\s*\n\s*([^\n]+)"
            name_match = re.search(name_pattern, text)
            if name_match:
                full_name = name_match.group(1).strip()
                name_parts = full_name.split()
                data['first_name'] = name_parts[0] if name_parts else ''
                data['last_name'] = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

            # Extraction de la photo du client
            b64_avatar = self._extract_avatar_base64_from_first_page(self.pdf_file)

            if b64_avatar:
                data['image_1920'] = b64_avatar  # ✅ prêt pour l’ORM

            # Extraction de l'URL du client
            uri = self._extract_first_uri_from_first_page(self.pdf_file)
            if uri:
                data['website'] = uri  # ✅ Ajout du lien Airbnb

            # Extraction du téléphone
            raw_phone, phone = self._extract_phone_from_pdf_annotations_fitz(self.pdf_file)
            if phone:
                data['phone'] = phone
                data['phone_raw'] = raw_phone
            else:
                text = self._extract_text_from_pdf(self.pdf_file) or ""
                m = re.search(r"(?:\\+?\\d[\\d\\s().-]{6,}\\d)", text)  # motif tolérant
                if m:
                    raw = m.group(0)
                    data['phone'] = ('+' + re.sub(r'\\D', '', raw[1:])) if raw.strip().startswith('+') else re.sub(
                        r'\\D', '', raw)
                    data['phone_raw'] = raw

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
                data['language'] = lang_mapping.get(lang_text, 'fr_FR')

            # Extraction du type de logement
            property_pattern = r"Ancien voyageur\s*\n\s*[^\n]+\n\s*([^\n]+)"
            property_match = re.search(property_pattern, text, re.IGNORECASE)
            if property_match:
                data['property_type'] = property_match.group(1).strip()

            # Extraction des dates
            self.extract_dates_from_pdf_text(data, text)

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
            total_pattern = r"Total \(EUR\)\s*([0-9\s\u00A0.,]+)\s*€"
            payment_section = re.search(r"Versement\s+de\s+l[''`]hôte", text, re.IGNORECASE)

            if not payment_section:
                payment_section = re.search(r"Détails\s+du\s+paiement\s+du\s+voyageur", text, re.IGNORECASE)

            total_match = re.search(total_pattern, text[payment_section.end():], re.IGNORECASE)

            if total_match:
                amount_str = total_match.group(1)
                # Nettoyer la chaîne pour la convertir en nombre
                cleaned_amount = amount_str.replace(' ', '').replace('\u00A0', '').replace(',', '.')
                data['rate'] = float(cleaned_amount)

            # Trouver tous les montants totaux
            all_totals = re.findall(total_pattern, text)
            if len(all_totals) >= 2 and self.env.company.hm_airbnb_vendor_platform_commission:
                guest_total = float(all_totals[0].replace(' ', '').replace('\u00A0', '').replace(',', '.'))
                host_total = float(all_totals[1].replace(' ', '').replace('\u00A0', '').replace(',', '.'))
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
                'name': name or 'Indéfini',
                'image_1920': data.get('image_1920', ''),
                'mobile': data.get('phone_raw', ''),
                'website': data.get('website', ''),
                'city': data.get('city', ''),
                'country_id': country.id if country else False,
                'lang': data.get('language', 'fr_FR'),
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

        # Convertir le montant EUR en XPF
        rate_xpf = data.get('rate', 0) * 1000 / 8.38  # taux plus précis
        commission_xpf = data.get('commission_amount', 0) * 1000 / 8.38

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
            'origin': data.get('origin', 'airbnb'),  # Définir l'origine comme Airbnb
            'import_type': data.get('import_type', 'pdf'),
        }

        # Supprimer les champs qui n'existent peut-être pas
        fields_to_check = ['children', 'booking_id', 'payment_status']
        for field_name in fields_to_check:
            if field_name in booking_vals:
                # Vérifier si le champ existe dans le modèle
                if field_name not in BookingLine._fields:
                    booking_vals.pop(field_name)

        booking_line = BookingLine.create(booking_vals)
        return booking_line

    def _get_or_create_property_type(self, property_description):
        """Trouve ou crée le type de propriété"""
        ProductTemplate = self.env['product.template']

        # Nettoyer la description
        clean_description = property_description.strip()

        # Rechercher un produit existant
        product = ProductTemplate.search([
            ('description_sale', 'ilike', clean_description)
        ], limit=1)

        if not product:
            # Créer un nouveau type de propriété
            product_vals = {
                'name': clean_description,
                'description_sale': clean_description,
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
            # Valoriser le type d'import
            self.import_id.import_type = 'pdf'

            # Valoriser l'origine de l'import
            self.import_id.origin = 'airbnb'

            # Extraction du texte
            text = self._extract_text_from_pdf(self.pdf_file)

            # Parsing des données
            data = self._parse_airbnb_data(text)

            # Création du partner
            partner = self._create_partner(data)

            # Création de la ligne de réservation
            booking_line = self._create_booking_line(data, partner)
            self._add_booking_line_to_booking_month(booking_line)

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

    def _add_booking_line_to_booking_month(self, booking_line):
        """
        Ajoute la ligne de réservation à la vue mensuelle appropriée.
        Crée la vue mensuelle si elle n'existe pas encore.
        """
        if not booking_line or not booking_line.arrival_date or not booking_line.property_type_id:
            _logger.warning(
                f"Impossible d'ajouter la réservation au mois : "
                f"données manquantes (arrival_date ou property_type_id)"
            )
            return

        BookingMonth = self.env['booking.month']

        # Extraire l'année et le mois de la date d'arrivée
        year = booking_line.arrival_date.year
        month = booking_line.arrival_date.month

        # Rechercher ou créer la vue mensuelle correspondante
        booking_month = BookingMonth.search([
            ('year', '=', year),
            ('month', '=', month),
            ('property_type_id', '=', booking_line.property_type_id.id),
            ('company_id', '=', booking_line.company_id.id or self.env.company.id)
        ], limit=1)

        if not booking_month:
            # Créer une nouvelle vue mensuelle
            try:
                booking_month = BookingMonth.create({
                    'year': year,
                    'month': month,
                    'property_type_id': booking_line.property_type_id.id,
                    'company_id': booking_line.company_id.id or self.env.company.id,
                })
                _logger.info(
                    f"Vue mensuelle créée : {booking_month.display_name} "
                    f"pour la réservation {booking_line.booking_reference}"
                )
            except Exception as e:
                _logger.error(
                    f"Erreur lors de la création de la vue mensuelle "
                    f"pour {year}/{month:02d} - {booking_line.property_type_id.name}: {e}"
                )
                return

        # Lier la réservation à la vue mensuelle
        booking_line.booking_month_id = booking_month.id

        # Forcer le recalcul des champs calculés de la vue mensuelle
        # en invalidant le cache pour que les compute se déclenchent
        booking_month.invalidate_recordset([
            'reservation_ids',
            'total_reservations',
            'total_nights',
            'total_guests',
            'total_revenue',
            'total_commission_booking',
            'total_tourist_tax',
            'concierge_commission',
            'net_revenue',
        ])

        _logger.info(
            f"Réservation {booking_line.booking_reference} ajoutée à "
            f"{booking_month.display_name} ({booking_month.total_reservations} réservations)"
        )

    def extract_dates_from_pdf_text(self, data, text):
        """
        Extrait les dates d'arrivée, départ et réservation d'un texte PDF
        basé sur le format observé dans l'image fournie
        """

        # Pattern pour les dates individuelles (format: jour. DD mois YYYY)
        # Exemple: "jeu. 27 févr. 2025" ou "dim. 2 mars 2025"
        date_pattern = r"(\w+)\.\s*(\d{1,2})\s+(\w+)\.?\s*(\d{4})"

        # Recherche de la date d'arrivée
        arrival_match = re.search(r"Arrivée.*?(\w+)\.\s*(\d{1,2})\s+(\w+)\.?\s*(\d{4})", text, re.IGNORECASE | re.DOTALL)
        if arrival_match:
            day = int(arrival_match.group(2))
            month_str = arrival_match.group(3)
            year = int(arrival_match.group(4))
            month = self._parse_french_month(month_str)
            if month:
                data['arrival_date'] = date(year, month, day)

        # Recherche de la date de départ
        departure_match = re.search(r"Départ.*?(\w+)\.\s*(\d{1,2})\s+(\w+)\.?\s*(\d{4})", text, re.IGNORECASE | re.DOTALL)
        if departure_match:
            day = int(departure_match.group(2))
            month_str = departure_match.group(3)
            year = int(departure_match.group(4))
            month = self._parse_french_month(month_str)
            if month:
                data['departure_date'] = date(year, month, day)

        # Recherche de la date de réservation
        reservation_match = re.search(r"Date de réservation.*?(\w+)\.\s*(\d{1,2})\s+(\w+)\.?\s*(\d{4})", text,
                                      re.IGNORECASE | re.DOTALL)
        if reservation_match:
            day = int(reservation_match.group(2))
            month_str = reservation_match.group(3)
            year = int(reservation_match.group(4))
            month = self._parse_french_month(month_str)
            if month:
                data['reservation_date'] = date(year, month, day)

        # Calcul du nombre de nuits si on a les dates d'arrivée et de départ
        if 'arrival_date' in data and 'departure_date' in data:
            duration = data['departure_date'] - data['arrival_date']
            data['duration_nights'] = duration.days

        return data

    def _parse_french_month(self, month_str):
        """
        Convertit les noms/abréviations de mois français en numéro de mois
        """
        french_months = {
            'janvier': 1, 'janv': 1, 'jan': 1,
            'février': 2, 'févr': 2, 'fev': 2, 'feb': 2,
            'mars': 3, 'mar': 3,
            'avril': 4, 'avr': 4, 'apr': 4,
            'mai': 5,
            'juin': 6, 'jun': 6,
            'juillet': 7, 'juil': 7, 'jul': 7,
            'août': 8, 'aou': 8, 'aug': 8,
            'septembre': 9, 'sept': 9, 'sep': 9,
            'octobre': 10, 'oct': 10,
            'novembre': 11, 'nov': 11,
            'décembre': 12, 'déc': 12, 'dec': 12
        }

        month_clean = month_str.lower().strip('.').strip()
        return french_months.get(month_clean)

# class BookingImport(models.Model):
#     _inherit = 'booking.import'
#     _description = 'Import de réservations'
#
#     def action_import_airbnb_pdf(self):
#         """Action pour ouvrir l'assistant d'import PDF"""
#         return {
#             'type': 'ir.actions.act_window',
#             'name': _('Importer PDF Airbnb'),
#             'view_mode': 'form',
#             'res_model': 'airbnb.pdf.importer',
#             'target': 'new',
#             'context': {'default_import_id': self.id}
#         }

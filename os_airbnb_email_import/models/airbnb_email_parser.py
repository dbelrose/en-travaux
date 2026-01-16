# -*- coding: utf-8 -*-
from odoo import models, api, _
import re
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class AirbnbEmailParser(models.TransientModel):
    _name = 'airbnb.email.parser'
    _description = 'Parser d\'emails Airbnb'

    # ============================================
    # PARSING PRINCIPAL
    # ============================================

    @api.model
    def parse_email_html(self, html_body, company):
        """
        Parse un email HTML Airbnb et extrait toutes les données
        
        Returns:
            dict: Données parsées ou False si échec
        """
        if not html_body:
            return False

        data = {
            'company_id': company.id,
            'origin': 'airbnb',
            'import_type': 'email',
        }

        try:
            # Extraction des données
            data['booking_reference'] = self._extract_confirmation_code(html_body)
            data['first_name'], data['last_name'] = self._extract_guest_name(html_body)
            data['city'] = self._extract_city(html_body)
            data['country'] = self._extract_country(html_body)
            data['property_type'] = self._extract_property_name(html_body)
            data['arrival_date'] = self._extract_arrival_date(html_body)
            data['departure_date'] = self._extract_departure_date(html_body)
            data['duration_nights'] = self._extract_duration(html_body)
            data['pax_nb'] = self._extract_travelers(html_body)
            data['rate_eur'] = self._extract_host_payout(html_body)
            data['commission_eur'] = self._extract_commission(html_body)

            # Validation des données critiques
            if not data['booking_reference']:
                _logger.warning("⚠️ Code de confirmation manquant")
                return False

            if not data['arrival_date'] or not data['departure_date']:
                _logger.warning("⚠️ Dates manquantes")
                return False

            _logger.info(f"✅ Email parsé : {data['booking_reference']} - {data['first_name']} {data['last_name']}")
            return data

        except Exception as e:
            _logger.error(f"❌ Erreur parsing email : {e}")
            return False

    # ============================================
    # EXTRACTION CODE CONFIRMATION
    # ============================================

    def _extract_confirmation_code(self, html):
        """
        Extrait le code de confirmation
        Pattern : HMRFYEX8YT, HMBN8DM43P, etc.
        """
        patterns = [
            r'CODE DE CONFIRMATION\s*\n?\s*([A-Z0-9]{10})',
            r'Code de confirmation\s*\n?\s*([A-Z0-9]{10})',
            r'Confirmation code\s*\n?\s*([A-Z0-9]{10})',
            r'>([A-Z0-9]{10})</p>',  # Fallback dans balise <p>
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    # ============================================
    # EXTRACTION NOM VOYAGEUR
    # ============================================

    def _extract_guest_name(self, html):
        """
        Extrait le nom du voyageur
        Pattern : "Nicolas", "Maryse", etc.
        """
        patterns = [
            r'<p class=[^>]*>([A-Z][a-zéèêàâôûïü]+)</p>',  # Prénom en <p>
            r'arrive bientôt.*?([A-Z][a-zéèêàâôûïü]+)',  # "Nicolas arrive bientôt"
            r'arriv.*?([A-Z][a-zéèêàâôûïü]+)\s+arrive',  # "Maryse arrivera"
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                first_name = match.group(1).strip()
                # Le nom de famille n'est pas disponible dans les emails Airbnb
                return first_name, ''

        return 'Voyageur', 'Airbnb'

    # ============================================
    # EXTRACTION LOCALISATION
    # ============================================

    def _extract_city(self, html):
        """Extrait la ville du voyageur"""
        patterns = [
            r'([A-Z][a-z\-]+(?:\s+[A-Z][a-z\-]+)*),\s+France',
            r'([A-Z][a-z\-]+(?:\s+[A-Z][a-z\-]+)*),\s+[A-Z]{2}',
            r'>([A-Z][a-z\-]+(?:\s+sur\s+[A-Z][a-z]+)?),\s+France<',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()

        return ''

    def _extract_country(self, html):
        """Extrait le pays du voyageur"""
        patterns = [
            r'[,\s]+([A-Z][a-z]+)\s*</p>',  # "Hauteville-sur-Fier, France</p>"
            r'[,\s]+(France|États-Unis|United States|Canada|Royaume-Uni)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1).strip()

        return ''

    # ============================================
    # EXTRACTION LOGEMENT
    # ============================================

    def _extract_property_name(self, html):
        """
        Extrait le nom du logement
        Pattern : "DUPLEX 4 CHAMBRES, DERNIER ÉTAGE, VUE OCÉAN"
        """
        patterns = [
            r'<h2[^>]*>([A-Z\s,ÉÈÊÀÂÔÛÏÜ0-9]+)</h2>',  # Titre H2 en majuscules
            r'Duplex[^<]*',  # Commence par "Duplex"
            r'DUPLEX[^<]*',  # Commence par "DUPLEX"
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                name = match.group(1) if '(' in pattern else match.group(0)
                # Nettoyage
                name = re.sub(r'<[^>]+>', '', name)  # Supprimer balises HTML
                name = name.strip()
                if len(name) > 10:  # Au moins 10 caractères
                    return name

        return 'Logement Airbnb'

    # ============================================
    # EXTRACTION DATES
    # ============================================

    def _extract_arrival_date(self, html):
        """
        Extrait la date d'arrivée
        Pattern : "sam. 16 août", "lun. 22 déc."
        """
        return self._extract_date_generic(html, r'Arrivée[^<]*<[^>]*>([^<]+)</p>')

    def _extract_departure_date(self, html):
        """Extrait la date de départ"""
        return self._extract_date_generic(html, r'Départ[^<]*<[^>]*>([^<]+)</p>')

    def _extract_date_generic(self, html, pattern):
        """
        Extrait et convertit une date française
        Pattern example : "sam. 16 août" → 2025-08-16
        """
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            return None

        date_str = match.group(1).strip()
        
        # Pattern : "lun. 22 déc." ou "sam. 16 août"
        date_match = re.search(r'(\d{1,2})\s+(\w+)', date_str)
        if not date_match:
            return None

        day = int(date_match.group(1))
        month_str = date_match.group(2).lower().replace('.', '')
        
        # Mapping mois français
        months = {
            'janv': 1, 'janvier': 1,
            'févr': 2, 'fév': 2, 'février': 2,
            'mars': 3,
            'avr': 4, 'avril': 4,
            'mai': 5,
            'juin': 6,
            'juil': 7, 'juillet': 7,
            'août': 8, 'aout': 8,
            'sept': 9, 'septembre': 9,
            'oct': 10, 'octobre': 10,
            'nov': 11, 'novembre': 11,
            'déc': 12, 'dec': 12, 'décembre': 12,
        }

        month = months.get(month_str)
        if not month:
            return None

        # Année : déterminer automatiquement (année courante ou suivante)
        now = datetime.now()
        year = now.year
        
        # Si la date est passée, c'est l'année prochaine
        try:
            test_date = datetime(year, month, day)
            if test_date < now:
                year += 1
        except ValueError:
            return None

        try:
            return datetime(year, month, day).date()
        except ValueError:
            return None

    # ============================================
    # EXTRACTION DURÉE & VOYAGEURS
    # ============================================

    def _extract_duration(self, html):
        """
        Extrait la durée du séjour
        Pattern : "7 nuits", "4 nuits"
        """
        patterns = [
            r'(\d+)\s*nuits?',
            r'(\d+)\s*nights?',
            r'pour\s+(\d+)\s*nuit',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 1

    def _extract_travelers(self, html):
        """
        Extrait le nombre de voyageurs
        Pattern : "3 adultes", "6 adultes"
        """
        patterns = [
            r'(\d+)\s*adultes?',
            r'(\d+)\s*adults?',
            r'(\d+)\s*voyageurs?',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return 1

    # ============================================
    # EXTRACTION MONTANTS
    # ============================================

    def _extract_host_payout(self, html):
        """
        Extrait le montant "Vous gagnez"
        Pattern : "698,58 €", "620,38 €"
        """
        patterns = [
            r'VOUS GAGNEZ\s*</h3>.*?([0-9\s,\.]+)\s*€',
            r'Vous gagnez\s*</h3>.*?([0-9\s,\.]+)\s*€',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                amount_str = match.group(1).strip()
                # Nettoyer : "698,58" → 698.58
                amount_str = amount_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
                try:
                    return float(amount_str)
                except ValueError:
                    continue

        return 0.0

    def _extract_commission(self, html):
        """
        Calcule la commission Airbnb
        Commission = Total voyageur - Versement hôte
        """
        # Extraire total voyageur
        total_pattern = r'TOTAL \(EUR\)\s*</h3>.*?([0-9\s,\.]+)\s*€'
        total_match = re.search(total_pattern, html, re.IGNORECASE | re.DOTALL)
        
        if not total_match:
            return 0.0

        total_str = total_match.group(1).strip().replace(' ', '').replace('\xa0', '').replace(',', '.')
        
        try:
            total_eur = float(total_str)
            host_payout = self._extract_host_payout(html)
            commission = total_eur - host_payout
            return max(commission, 0.0)
        except ValueError:
            return 0.0

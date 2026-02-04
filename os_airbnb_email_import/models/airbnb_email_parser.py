# -*- coding: utf-8 -*-
from odoo import models, api, _
import re
from datetime import datetime
import logging
import quopri

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
            data['guest_photo_url'] = self._extract_guest_photo(html_body)
            data['city'] = self._extract_city(html_body)

            # CORRECTION TODO 2: Extraction pays améliorée
            data['country'] = self._extract_country(html_body)

            data['property_type'] = self._extract_property_name(html_body)
            data['arrival_date'] = self._extract_arrival_date(html_body)
            data['departure_date'] = self._extract_departure_date(html_body)
            data['duration_nights'] = self._extract_duration(html_body)
            data['pax_nb'] = self._extract_travelers(html_body)

            # CORRECTION TODO 3: Extraction montant avec debug renforcé
            data['rate_eur'] = self._extract_host_payout(html_body)
            data['commission_eur'] = self._extract_commission(html_body)

            # DEBUG RENFORCÉ: Afficher toutes les données extraites
            _logger.info(f"🔍 DEBUG Données extraites:")
            _logger.info(f"  - Dates: Arrivée={data.get('arrival_date')}, Départ={data.get('departure_date')}")
            _logger.info(f"  - Montants: rate_eur={data.get('rate_eur')}, commission_eur={data.get('commission_eur')}")
            _logger.info(f"  - Localisation: city={data.get('city')}, country={data.get('country')}")

            # Validation des données critiques
            if not data['booking_reference']:
                _logger.warning("⚠️ Code de confirmation manquant")
                return False

            if not data['arrival_date'] or not data['departure_date']:
                _logger.warning("⚠️ Dates manquantes")
                self._debug_date_extraction(html_body)
                return False

            _logger.info(f"✅ Email parsé : {data['booking_reference']} - {data['first_name']} {data['last_name']}")

            # NOUVEAU: Log final du montant pour traçabilité
            _logger.info(f"💰 Montant final parsé: {data['rate_eur']} EUR")

            return data

        except Exception as e:
            _logger.error(f"❌ Erreur parsing email : {e}")
            import traceback
            _logger.error(traceback.format_exc())
            return False

    # ============================================
    # DEBUG DATES
    # ============================================

    def _debug_date_extraction(self, html):
        """Affiche des extraits du HTML pour debugger les dates"""
        arrival_matches = re.finditer(r'Arrivée.{0,200}', html, re.IGNORECASE | re.DOTALL)
        for match in list(arrival_matches)[:2]:
            _logger.info(f"🔍 Extrait 'Arrivée' trouvé: {match.group(0)[:150]}...")

        departure_matches = re.finditer(r'Départ.{0,200}', html, re.IGNORECASE | re.DOTALL)
        for match in list(departure_matches)[:2]:
            _logger.info(f"🔍 Extrait 'Départ' trouvé: {match.group(0)[:150]}...")

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
            r'>([A-Z0-9]{10})</p>',
            r'code[^>]*>([A-Z0-9]{10})',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                code = match.group(1).strip()
                _logger.info(f"✅ Code confirmation trouvé: {code}")
                return code

        _logger.warning("⚠️ Code de confirmation non trouvé")
        return None

    # ============================================
    # EXTRACTION NOM VOYAGEUR
    # ============================================

    def _extract_guest_name(self, html):
        """
        Extrait le nom du voyageur depuis l'email (corps) ou le sujet
        """
        first_name = None
        last_name = ''

        html_clean = html.replace('&nbsp;', ' ').replace('\xa0', ' ')

        # Pattern 1 : Avec balises spéciales ⁨...⁩
        subject_pattern_with_marks = r'⁨([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s+[A-Z]\.)?(?:\s+(?:de|De|du|Du|van|Von|der|Der|Le|le|La|la))?(?:\s+[A-ZÀ-Ö][a-zà-öø-ÿ]+)*)⁩'
        match = re.search(subject_pattern_with_marks, html_clean)

        if match:
            full_name = match.group(1).strip()
            _logger.info(f"🔍 Nom extrait du sujet (avec balises): '{full_name}'")
            first_name, last_name = self._parse_full_name(full_name)
            return first_name, last_name

        # Pattern 2 : Dans le sujet sans balises
        subject_pattern_simple = r':\s*([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)\s+([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)\s+arrive\s+le'
        match = re.search(subject_pattern_simple, html_clean, re.IGNORECASE)

        if match:
            first_name = match.group(1).strip()
            last_name = match.group(2).strip()
            _logger.info(f"✅ Nom extrait du sujet (simple): Prénom='{first_name}', Nom='{last_name}'")
            return first_name, last_name

        # Pattern 3 : Format plus permissif
        subject_pattern_permissive = r'([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)\s+([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+).*?arrive'
        match = re.search(subject_pattern_permissive, html_clean, re.IGNORECASE)

        if match:
            first_name = match.group(1).strip()
            last_name = match.group(2).strip()
            _logger.info(f"✅ Nom extrait (permissif): Prénom='{first_name}', Nom='{last_name}'")
            return first_name, last_name

        # Pattern 4 : Depuis le corps de l'email
        patterns_body = [
            r'<p class=[^>]*>([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)</p>',
            r'arrive bientôt.*?([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)',
            r'arriv.*?([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)\s+arrive',
            r'>([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿëï]+)<.*?arrive',
        ]

        for pattern in patterns_body:
            match = re.search(pattern, html_clean, re.IGNORECASE | re.DOTALL)
            if match:
                first_name = match.group(1).strip()
                _logger.info(f"✅ Prénom voyageur trouvé (corps): {first_name}")
                return first_name, ''

        _logger.warning("⚠️ Nom voyageur non trouvé")
        return 'Voyageur', 'Airbnb'

    def _parse_full_name(self, full_name):
        """Parse un nom complet en prénom et nom"""
        name_parts = full_name.split()
        if len(name_parts) >= 1:
            first_name = name_parts[0]
            if len(name_parts) > 1:
                remaining = []
                for part in name_parts[1:]:
                    if len(part) > 2 or not part.endswith('.'):
                        remaining.append(part)

                if remaining:
                    last_name = ' '.join(remaining)
                else:
                    last_name = ''
            else:
                last_name = ''

            _logger.info(f"✅ Nom parsé: Prénom='{first_name}', Nom='{last_name}'")
            return first_name, last_name

        return 'Voyageur', 'Airbnb'

    # ============================================
    # EXTRACTION PHOTO PROFIL
    # ============================================

    def _extract_guest_photo(self, html):
        """Extrait l'URL de la photo de profil du voyageur"""
        patterns = [
            r'<img[^>]*src=["\']([^"\']*a0\.muscache\.com/im/pictures/user[^"\']*)["\']',
            r'src=["\']([^"\']*muscache\.com[^"\']*User[^"\']*\.jpe?g[^"\']*)["\']',
            r'<img[^>]*src=["\']([^"\']*muscache\.com/im/pictures/user/[^"\']+\.jpe?g[^"\']*)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                photo_url = match.group(1).strip()
                if 'logo' not in photo_url.lower() and 'brand' not in photo_url.lower():
                    _logger.info(f"✅ Photo profil trouvée: {photo_url[:80]}...")
                    return photo_url

        _logger.info("ℹ️ Photo profil non trouvée")
        return False

    # ============================================
    # EXTRACTION LOCALISATION - CORRECTION TODO 2
    # ============================================

    def _extract_city(self, html):
        """Extrait la ville du voyageur"""
        html_clean = self._clean_quoted_printable(html)

        # Pattern strict : chercher UNIQUEMENT après une image de profil utilisateur
        photo_patterns = [
            r'<img[^>]*src="[^"]*muscache\.com/im/pictures/user[^"]*"[^>]*>([^<,]+),\s*([^<]+)</p>',
            r'<img[^>]*src="[^"]*muscache\.com[^"]*User[^"]*"[^>]*>([^<,]+),\s*([^<]+)</p>',
        ]

        for pattern in photo_patterns:
            match = re.search(pattern, html_clean, re.IGNORECASE)
            if match:
                city = match.group(1).strip()
                # Validation : une ville ne devrait pas être un code de 2 lettres
                if len(city) > 2:
                    _logger.info(f"✅ Ville trouvée: {city}")
                    return city

        _logger.info("ℹ️ Ville non indiquée dans l'email")
        return ''

    def _extract_country(self, html):
        """
        CORRECTION TODO 2: Extrait le pays du voyageur de manière plus robuste

        Stratégie :
        1. Chercher le pays UNIQUEMENT après la photo de profil utilisateur
        2. Exclure les codes à 2 lettres isolés (probablement des codes pays ailleurs)
        3. Valider la cohérence (longueur, position)
        """
        html_clean = self._clean_quoted_printable(html)

        # Pattern ultra-spécifique : APRÈS une image de profil utilisateur (muscache.com/im/pictures/user)
        # et AVANT la balise de fermeture </p>
        photo_patterns = [
            # Pattern 1 : Image user suivie de "Ville, Pays</p>"
            r'<img[^>]*src="[^"]*muscache\.com/im/pictures/user[^"]*"[^>]*>([^<]+)</p>',
            # Pattern 2 : Image user avec User dans l'URL
            r'<img[^>]*src="[^"]*muscache\.com[^"]*User[^"]*"[^>]*>([^<]+)</p>',
        ]

        for pattern in photo_patterns:
            match = re.search(pattern, html_clean, re.IGNORECASE)

            if match:
                location_text = match.group(1).strip()
                _logger.info(f"🔍 Localisation brute après photo: '{location_text}'")

                # Nettoyer les balises HTML résiduelles
                location_text = re.sub(r'<[^>]+>', '', location_text)
                location_text = location_text.strip()

                # Parser "Ville, Pays" ou "Pays"
                if ',' in location_text:
                    # Format "Ville, Pays" - prendre ce qui est après la DERNIÈRE virgule
                    parts = location_text.split(',')
                    country = parts[-1].strip()
                else:
                    # Format "Pays" seul
                    country = location_text.strip()

                # VALIDATION RENFORCÉE:
                # - Le pays doit faire au moins 3 caractères (exclure codes 2 lettres isolés)
                # - Maximum 30 caractères (éviter de capturer du texte parasite)
                # - Doit contenir au moins une lettre
                if country and len(country) >= 3 and len(country) <= 30 and re.search(r'[a-zA-ZÀ-ÿ]', country):
                    _logger.info(f"✅ Pays voyageur trouvé: '{country}'")
                    return country
                else:
                    _logger.warning(f"⚠️ Pays rejeté (validation): '{country}' (longueur: {len(country)})")

        # Fallback : chercher dans le contexte large UNIQUEMENT si rien trouvé
        # (mais avec validation stricte)
        fallback_pattern = r'(?:Ville|City)[^:]*:\s*([^,<]+),\s*([^<]+)</p>'
        match = re.search(fallback_pattern, html_clean, re.IGNORECASE)
        if match:
            country = match.group(2).strip()
            if len(country) >= 3 and len(country) <= 30:
                _logger.info(f"✅ Pays trouvé (fallback): '{country}'")
                return country

        _logger.info("ℹ️ Pays voyageur non indiqué dans l'email")
        return ''

    def _clean_quoted_printable(self, text):
        """Nettoie l'encodage Quoted-Printable dans le HTML"""
        try:
            text_no_breaks = re.sub(r'=\s*\n\s*', '', text)
            decoded = quopri.decodestring(text_no_breaks.encode('utf-8')).decode('utf-8', errors='ignore')
            return decoded
        except Exception as e:
            _logger.warning(f"⚠️ Erreur décodage Quoted-Printable: {e}")
            text = re.sub(r'=\s*\n\s*', '', text)
            text = text.replace('=3D', '=')
            text = text.replace('=20', ' ')
            text = text.replace('=0A', '\n')
            text = text.replace('=0D', '\r')
            return text

    # ============================================
    # EXTRACTION LOGEMENT
    # ============================================

    def _extract_property_name(self, html):
        """Extrait le nom du logement"""
        patterns = [
            r'<h2[^>]*>([A-Z\s,ÉÈÊÀÂÔÛÏÜ0-9]+)</h2>',
            r'Duplex[^<]*',
            r'DUPLEX[^<]*',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                name = match.group(1) if '(' in pattern else match.group(0)
                name = re.sub(r'<[^>]+>', '', name)
                name = name.strip()
                if len(name) > 10:
                    return name

        return 'Logement Airbnb'

    # ============================================
    # EXTRACTION DATES
    # ============================================

    def _extract_arrival_date(self, html):
        """Extrait la date d'arrivée"""
        patterns = [
            r'Arrivée[^<]*<[^>]*>([^<]+)</p>',
            r'Arrivée[:\s]*<[^>]*>([^<]+)<',
            r'Arrivée[:\s]*([a-z]{3,4}\.\s+\d{1,2}\s+[a-zéû]{3,9})',
            r'>Arrivée<.*?>([^<]+)<',
        ]

        for pattern in patterns:
            result = self._extract_date_generic(html, pattern)
            if result:
                _logger.info(f"✅ Date arrivée trouvée: {result}")
                return result

        _logger.warning("⚠️ Date d'arrivée non trouvée")
        return None

    def _extract_departure_date(self, html):
        """Extrait la date de départ"""
        patterns = [
            r'Départ[^<]*<[^>]*>([^<]+)</p>',
            r'Départ[:\s]*<[^>]*>([^<]+)<',
            r'Départ[:\s]*([a-z]{3,4}\.\s+\d{1,2}\s+[a-zéû]{3,9})',
            r'>Départ<.*?>([^<]+)<',
        ]

        for pattern in patterns:
            result = self._extract_date_generic(html, pattern)
            if result:
                _logger.info(f"✅ Date départ trouvée: {result}")
                return result

        _logger.warning("⚠️ Date de départ non trouvée")
        return None

    def _extract_date_generic(self, html, pattern):
        """Extrait et convertit une date française"""
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            return None

        date_str = match.group(1).strip()
        date_str = re.sub(r'<[^>]+>', '', date_str)
        date_str = re.sub(r'\s+', ' ', date_str)
        date_str = date_str.strip()

        _logger.info(f"🔍 Date string nettoyée: '{date_str}'")

        date_patterns = [
            r'(\d{1,2})\s+([a-zéû]{3,9})\.?\s*(\d{4})?',
            r'[a-z]{3,4}\.\s+(\d{1,2})\s+([a-zéû]{3,9})\.?\s*(\d{4})?',
        ]

        for date_pattern in date_patterns:
            date_match = re.search(date_pattern, date_str, re.IGNORECASE)
            if date_match:
                groups = date_match.groups()
                day = int(groups[0])
                month_str = groups[1].lower().replace('.', '')
                year_str = groups[2] if len(groups) > 2 else None

                months = {
                    'janv': 1, 'janvier': 1, 'jan': 1,
                    'févr': 2, 'fév': 2, 'février': 2, 'fev': 2, 'fevrier': 2,
                    'mars': 3, 'mar': 3,
                    'avr': 4, 'avril': 4,
                    'mai': 5,
                    'juin': 6, 'jun': 6,
                    'juil': 7, 'juillet': 7, 'jul': 7,
                    'août': 8, 'aout': 8, 'aoû': 8, 'aou': 8, 'aug': 8,
                    'sept': 9, 'septembre': 9, 'sep': 9,
                    'oct': 10, 'octobre': 10,
                    'nov': 11, 'novembre': 11,
                    'déc': 12, 'dec': 12, 'décembre': 12, 'decembre': 12,
                }

                month = months.get(month_str)
                if not month:
                    continue

                if year_str:
                    year = int(year_str)
                else:
                    now = datetime.now()
                    year = now.year
                    try:
                        test_date = datetime(year, month, day)
                        if test_date < now:
                            year += 1
                    except ValueError:
                        continue

                try:
                    result_date = datetime(year, month, day).date()
                    return result_date
                except ValueError:
                    continue

        return None

    # ============================================
    # EXTRACTION DURÉE & VOYAGEURS
    # ============================================

    def _extract_duration(self, html):
        """Extrait la durée du séjour"""
        html_clean = html.replace('&nbsp;', ' ').replace('\xa0', ' ')

        patterns = [
            r'(\d+)\s*nuits?',
            r'(\d+)\s*nights?',
            r'pour\s+(\d+)\s*nuit',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_clean, re.IGNORECASE)
            if match:
                duration = int(match.group(1))
                _logger.info(f"✅ Durée trouvée: {duration} nuit(s)")
                return duration

        _logger.warning("⚠️ Durée non trouvée, défaut: 1 nuit")
        return 1

    def _extract_travelers(self, html):
        """Extrait le nombre de voyageurs"""
        html_clean = html.replace('&nbsp;', ' ').replace('\xa0', ' ')

        patterns = [
            r'(\d+)\s*adultes?',
            r'(\d+)\s*adults?',
            r'(\d+)\s*voyageurs?',
        ]

        for pattern in patterns:
            match = re.search(pattern, html_clean, re.IGNORECASE)
            if match:
                travelers = int(match.group(1))
                _logger.info(f"✅ Voyageurs trouvés: {travelers}")
                return travelers

        _logger.warning("⚠️ Nombre de voyageurs non trouvé, défaut: 1")
        return 1

    # ============================================
    # EXTRACTION MONTANTS - DEBUG RENFORCÉ (TODO 3)
    # ============================================

    def _extract_host_payout(self, html):
        """
        Extrait le montant "Vous gagnez"
        DEBUG RENFORCÉ pour tracer le problème TODO 3
        """
        _logger.info("🔍 === DÉBUT EXTRACTION MONTANT HÔTE ===")

        html_clean = html.replace('&nbsp;', ' ').replace('\xa0', ' ')
        html_clean = self._clean_quoted_printable(html_clean)

        # Debug: afficher un extrait autour de "VOUS GAGNEZ"
        vous_gagnez_matches = re.finditer(r'VOUS GAGNEZ.{0,300}', html_clean, re.IGNORECASE | re.DOTALL)
        for match in list(vous_gagnez_matches)[:2]:
            _logger.info(f"🔍 Contexte 'VOUS GAGNEZ': {match.group(0)[:200]}...")

        patterns = [
            r'VOUS GAGNEZ\s*</h3>.*?([0-9\s,\.]+)\s*€',
            r'Vous gagnez\s*</h3>.*?([0-9\s,\.]+)\s*€',
            r'Vous gagnez.*?([0-9\s,\.]+)\s*€',
            # Nouveau pattern plus permissif
            r'(?:VOUS GAGNEZ|Vous gagnez)[^€]*?([0-9\s,\.]+)\s*€',
        ]

        for idx, pattern in enumerate(patterns):
            _logger.info(f"🔍 Test pattern {idx + 1}: {pattern[:50]}...")
            match = re.search(pattern, html_clean, re.IGNORECASE | re.DOTALL)
            if match:
                amount_str = match.group(1).strip()
                _logger.info(f"✅ Montant brut trouvé avec pattern {idx + 1}: '{amount_str}'")

                # Nettoyer
                amount_str = amount_str.replace(' ', '')
                amount_str = amount_str.replace(',', '.')

                _logger.info(f"🔍 Montant nettoyé: '{amount_str}'")

                try:
                    amount = float(amount_str)
                    _logger.info(f"✅✅✅ MONTANT HÔTE FINAL: {amount} EUR")
                    return amount
                except ValueError as e:
                    _logger.warning(f"⚠️ Erreur conversion montant: {e}")
                    continue

        _logger.warning("⚠️⚠️⚠️ MONTANT HÔTE NON TROUVÉ, retour 0.0")
        return 0.0

    def _extract_commission(self, html):
        """Calcule la commission Airbnb"""
        html_clean = html.replace('&nbsp;', ' ').replace('\xa0', ' ')

        total_patterns = [
            r'TOTAL \(EUR\)\s*</h3>.*?([0-9\s,\.]+)\s*€',
            r'TOTAL.*?([0-9\s,\.]+)\s*€',
        ]

        total_match = None
        for pattern in total_patterns:
            total_match = re.search(pattern, html_clean, re.IGNORECASE | re.DOTALL)
            if total_match:
                break

        if not total_match:
            _logger.warning("⚠️ Total voyageur non trouvé, commission = 0.0")
            return 0.0

        total_str = total_match.group(1).strip().replace(' ', '').replace(',', '.')

        try:
            total_eur = float(total_str)
            host_payout = self._extract_host_payout(html)
            commission = total_eur - host_payout
            _logger.info(f"✅ Commission calculée: {commission:.2f} EUR (Total: {total_eur} - Hôte: {host_payout})")
            return max(commission, 0.0)
        except ValueError:
            _logger.warning("⚠️ Erreur calcul commission, défaut: 0.0")
            return 0.0
        
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import base64
import requests

_logger = logging.getLogger(__name__)


class AirbnbEmailProcessor(models.TransientModel):
    _name = 'airbnb.email.processor'
    _description = 'Processeur de réservations Airbnb depuis email'

    # ============================================
    # TRAITEMENT RÉSERVATION
    # ============================================

    @api.model
    def process_reservation(self, parsed_data, company, lead):
        """
        Crée la réservation complète depuis les données parsées

        Args:
            parsed_data: Données extraites du email
            company: res.company
            lead: crm.lead

        Returns:
            booking.import.line: La réservation créée
        """
        # DEBUG: Afficher les données reçues du parser
        _logger.info("=" * 80)
        _logger.info("🔍 PROCESSOR - Données reçues du parser:")
        _logger.info(f"  - booking_reference: {parsed_data.get('booking_reference')}")
        _logger.info(f"  - first_name: {parsed_data.get('first_name')}")
        _logger.info(f"  - last_name: {parsed_data.get('last_name')}")
        _logger.info(f"  - rate_eur: {parsed_data.get('rate_eur')} EUR")
        _logger.info(f"  - commission_eur: {parsed_data.get('commission_eur')} EUR")
        _logger.info(f"  - country: {parsed_data.get('country')}")
        _logger.info("=" * 80)

        # 0. Créer l'import header
        booking_import = self._create_booking_import(parsed_data, company)

        # 1. Créer ou récupérer le contact (CORRECTION TODO 1)
        partner = self._create_or_get_partner(parsed_data, company)

        # 2. Trouver ou créer le logement
        property_type = self._find_or_create_property(parsed_data, company)

        # 3. Créer la réservation (CORRECTION TODO 3)
        booking_line = self._create_booking_line(parsed_data, partner, property_type, company, booking_import)

        # 4. Mettre à jour le lead CRM
        self._update_lead(lead, booking_line, partner, company)

        # 5. Lier aux vues mensuelles/trimestrielles
        self._link_to_periods(booking_line)

        return booking_line

    # ============================================
    # CRÉATION IMPORT HEADER
    # ============================================

    def _create_booking_import(self, data, company):
        """
        Crée l'enregistrement booking.import pour l'import email
        """
        BookingImport = self.env['booking.import'].sudo()

        import_name = f"Email Airbnb - {data.get('booking_reference', 'N/A')} - {fields.Date.today()}"

        booking_import = BookingImport.create({
            'name': import_name,
            'import_type': 'email',
            'origin': 'airbnb',
            'state': 'imported',
            'company_id': company.id,
            'import_date': fields.Datetime.now(),
        })

        _logger.info(f"✅ Import créé : {booking_import.name} (ID: {booking_import.id})")
        return booking_import

    # ============================================
    # CRÉATION/RÉCUPÉRATION CONTACT - CORRECTION TODO 1
    # ============================================

    def _create_or_get_partner(self, data, company):
        """
        CORRECTION TODO 1: Crée ou récupère le contact client sans créer de doublons

        Stratégie:
        1. Recherche par first_name + last_name (si module partner_firstname installé)
        2. OU recherche par name complet
        3. Met à jour les infos (photo, ville, pays) si partner trouvé
        4. Crée un nouveau partner seulement si introuvable
        """
        Partner = self.env['res.partner'].sudo()

        first_name = data.get('first_name', 'Voyageur')
        last_name = data.get('last_name', '')  # Peut être vide

        _logger.info(f"🔍 PROCESSOR - Recherche partner: first_name='{first_name}', last_name='{last_name}'")

        # ÉTAPE 1: Recherche d'un partner existant
        partner = None

        # Option A: Si le module partner_firstname est installé (champs firstname/lastname existent)
        if 'firstname' in Partner._fields:
            _logger.info("📋 Module partner_firstname détecté, recherche par firstname/lastname")
            domain = [
                ('firstname', '=', first_name),
                ('company_id', '=', company.id),
            ]
            # Ajouter lastname à la recherche seulement s'il est renseigné
            if last_name:
                domain.append(('lastname', '=', last_name))

            partner = Partner.search(domain, limit=1)

        # Option B: Recherche par nom complet (champ 'name' standard)
        else:
            _logger.info("📋 Recherche par champ 'name' standard")
            full_name = f"{first_name} {last_name}".strip()
            partner = Partner.search([
                ('name', '=', full_name),
                ('company_id', '=', company.id),
            ], limit=1)

        # ÉTAPE 2: Si partner trouvé, le mettre à jour
        if partner:
            _logger.info(f"✅ Partner existant trouvé: {partner.name} (ID: {partner.id})")

            # Collecter les mises à jour
            update_vals = {}

            # Mettre à jour la photo si disponible et pas déjà présente
            if data.get('guest_photo_url') and not partner.image_1920:
                _logger.info("📸 Mise à jour photo profil...")
                photo_base64 = self._download_photo_to_base64(data['guest_photo_url'])
                if photo_base64:
                    update_vals['image_1920'] = photo_base64

            # Mettre à jour la ville si manquante
            if data.get('city') and not partner.city:
                _logger.info(f"🏙️ Mise à jour ville: {data.get('city')}")
                update_vals['city'] = data['city']

            # Mettre à jour le pays si manquant
            if data.get('country') and not partner.country_id:
                country = self._get_country_id(data['country'])
                if country:
                    _logger.info(f"🌍 Mise à jour pays: {country.name}")
                    update_vals['country_id'] = country.id

            # Appliquer les mises à jour
            if update_vals:
                partner.write(update_vals)
                _logger.info(f"📝 Partner mis à jour avec: {list(update_vals.keys())}")
            else:
                _logger.info("ℹ️ Aucune mise à jour nécessaire")

            return partner

        # ÉTAPE 3: Créer un nouveau partner
        _logger.info(f"➕ Création nouveau partner: {first_name} {last_name}")
        return self._create_new_partner(data, first_name, last_name, company)

    def _create_new_partner(self, data, first_name, last_name, company):
        """Crée un nouveau partner depuis les données parsées"""
        Partner = self.env['res.partner'].sudo()

        # Récupération du pays
        country = self._get_country_id(data.get('country'))

        # Récupération catégorie Airbnb
        try:
            airbnb_category = self.env.ref('os_airbnb_pdf_import.res_partner_category_plateforme_airbnb')
        except:
            airbnb_category = False

        # Préparer les valeurs
        partner_vals = {
            'city': data.get('city', ''),
            'country_id': country.id if country else False,
            'company_id': company.id,
            'is_company': False,
            'customer_rank': 1,
            'category_id': [(6, 0, [airbnb_category.id])] if airbnb_category else [],
        }

        # Ajouter firstname/lastname OU name selon le module installé
        if 'firstname' in Partner._fields:
            # Module partner_firstname installé
            partner_vals['firstname'] = first_name
            partner_vals['lastname'] = last_name if last_name else 'Airbnb'
        else:
            # Odoo standard, utiliser 'name'
            full_name = f"{first_name} {last_name}".strip()
            partner_vals['name'] = full_name if full_name else 'Voyageur Airbnb'

        # Créer le partner
        partner = Partner.create(partner_vals)
        _logger.info(f"✅ Partner créé: {partner.name} (ID: {partner.id})")

        # Télécharger la photo si disponible
        if data.get('guest_photo_url'):
            photo_base64 = self._download_photo_to_base64(data['guest_photo_url'])
            if photo_base64:
                partner.write({'image_1920': photo_base64})

        return partner

    def _get_country_id(self, country_name):
        """
        Trouve le res.country à partir du nom
        Gère les variations (France, france, FR, etc.)
        """
        if not country_name:
            return None

        _logger.info(f"🔍 Recherche pays: '{country_name}'")

        # Recherche exacte par nom
        country = self.env['res.country'].sudo().search([
            ('name', '=ilike', country_name)
        ], limit=1)

        if country:
            _logger.info(f"✅ Pays trouvé (exact): {country.name} ({country.code})")
            return country

        # Recherche par code ISO (si c'est un code à 2 lettres)
        if len(country_name) == 2:
            country = self.env['res.country'].sudo().search([
                ('code', '=ilike', country_name)
            ], limit=1)
            if country:
                _logger.info(f"✅ Pays trouvé (code): {country.name} ({country.code})")
                return country

        # Recherche partielle (contient)
        country = self.env['res.country'].sudo().search([
            ('name', 'ilike', country_name)
        ], limit=1)

        if country:
            _logger.info(f"✅ Pays trouvé (partiel): {country.name} ({country.code})")
        else:
            _logger.warning(f"⚠️ Pays non trouvé pour: '{country_name}'")

        return country

    def _download_photo_to_base64(self, photo_url):
        """Télécharge une image et la convertit en base64 pour Odoo"""
        try:
            _logger.info(f"📥 Téléchargement photo: {photo_url[:80]}...")
            response = requests.get(photo_url, timeout=10)

            if response.status_code == 200:
                image_base64 = base64.b64encode(response.content)
                _logger.info("✅ Photo téléchargée avec succès")
                return image_base64
            else:
                _logger.warning(f"⚠️ Échec téléchargement photo (HTTP {response.status_code})")
                return None
        except Exception as e:
            _logger.warning(f"⚠️ Erreur téléchargement photo: {e}")
            return None

    # ============================================
    # RECHERCHE/CRÉATION LOGEMENT
    # ============================================

    def _find_or_create_property(self, data, company):
        """
        Trouve ou crée le logement via description_sale
        """
        ProductTemplate = self.env['product.template'].sudo()

        property_name = data.get('property_type', 'Logement Airbnb')

        # 1. Recherche exacte
        property_type = ProductTemplate.search([
            ('description_sale', '=', property_name),
            '|',
            ('company_id', '=', company.id),
            ('company_id', '=', False)
        ], limit=1)

        if property_type:
            _logger.info(f"✅ Logement trouvé (exact) : {property_type.name}")
            return property_type

        # 2. Recherche partielle (mots-clés)
        keywords = self._extract_keywords(property_name)
        for keyword in keywords:
            property_type = ProductTemplate.search([
                ('description_sale', 'ilike', keyword),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False)
            ], limit=1)

            if property_type:
                _logger.info(f"✅ Logement trouvé (partiel) : {property_type.name} via '{keyword}'")
                return property_type

        # 3. Création nouveau logement
        _logger.info(f"➕ Création nouveau logement : {property_name}")

        property_type = ProductTemplate.create({
            'name': property_name,
            'description_sale': property_name,
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': False,
            'company_id': company.id,
            'categ_id': self._get_accommodation_category().id,
        })

        _logger.info(f"✅ Logement créé : {property_type.name} (ID: {property_type.id})")
        return property_type

    def _extract_keywords(self, property_name):
        """Extrait les mots-clés principaux pour la recherche"""
        cleaned = property_name.upper().replace(',', ' ')
        words = [w for w in cleaned.split() if len(w) > 3]
        return words[:3]

    def _get_accommodation_category(self):
        """Retourne ou crée la catégorie Hébergements"""
        category = self.env['product.category'].sudo().search([
            ('name', '=', 'Hébergements')
        ], limit=1)

        if not category:
            category = self.env['product.category'].sudo().create({
                'name': 'Hébergements'
            })

        return category

    # ============================================
    # CRÉATION RÉSERVATION - CORRECTION TODO 3
    # ============================================

    def _create_booking_line(self, data, partner, property_type, company, booking_import):
        """
        CORRECTION TODO 3: Crée la ligne de réservation avec gestion robuste des montants
        """
        BookingLine = self.env['booking.import.line'].sudo()

        # DEBUG: Afficher le montant EUR reçu
        rate_eur = data.get('rate_eur', 0)
        commission_eur = data.get('commission_eur', 0)

        _logger.info("=" * 80)
        _logger.info("💰 PROCESSOR - CONVERSION MONTANTS:")
        _logger.info(f"  📥 rate_eur reçu du parser: {rate_eur} EUR")
        _logger.info(f"  📥 commission_eur reçu du parser: {commission_eur} EUR")

        # CORRECTION TODO 3: Conversion EUR → XPF avec validation
        try:
            rate_xpf = company.convert_eur_to_xpf(rate_eur)
            commission_xpf = company.convert_eur_to_xpf(commission_eur)

            _logger.info(f"  ✅ Après convert_eur_to_xpf():")
            _logger.info(f"     - rate_xpf: {rate_xpf}")
            _logger.info(f"     - commission_xpf: {commission_xpf}")

            # Validation: si la conversion retourne None ou 0 alors que EUR > 0
            if rate_eur > 0 and (rate_xpf is None or rate_xpf == 0):
                _logger.error(f"❌ ERREUR: convert_eur_to_xpf a retourné {rate_xpf} pour {rate_eur} EUR")
                # Fallback: conversion manuelle
                rate_xpf = rate_eur * 119.33
                commission_xpf = commission_eur * 119.33
                _logger.warning(f"⚠️ Utilisation taux de change manuel: {rate_xpf:.2f} XPF")

        except AttributeError:
            _logger.error("❌ ERREUR: Méthode convert_eur_to_xpf() n'existe pas sur res.company")
            # Fallback: conversion manuelle avec taux EUR/XPF = 119.33
            rate_xpf = rate_eur * 119.33
            commission_xpf = commission_eur * 119.33
            _logger.warning(f"⚠️ Conversion manuelle: {rate_eur} EUR → {rate_xpf:.2f} XPF")
        except Exception as e:
            _logger.error(f"❌ Erreur inattendue lors de la conversion: {e}")
            rate_xpf = rate_eur * 119.33
            commission_xpf = commission_eur * 119.33
            _logger.warning(f"⚠️ Conversion manuelle (erreur): {rate_xpf:.2f} XPF")

        _logger.info(f"  💵 MONTANTS FINAUX:")
        _logger.info(f"     - rate_xpf: {rate_xpf:.2f} XPF")
        _logger.info(f"     - commission_xpf: {commission_xpf:.2f} XPF")
        _logger.info("=" * 80)

        # Création de la réservation
        booking_vals = {
            'partner_id': partner.id,
            'booker_id': partner.id,
            'property_type_id': property_type.id,
            'company_id': company.id,
            'arrival_date': data.get('arrival_date'),
            'departure_date': data.get('departure_date'),
            'reservation_date': fields.Date.today(),
            'duration_nights': data.get('duration_nights', 1),
            'pax_nb': data.get('pax_nb', 1),
            'children': 0,  # Non disponible dans les emails
            'booking_reference': data.get('booking_reference', ''),
            'status': 'ok',
            'rate': rate_xpf,
            'commission_amount': commission_xpf,
            'origin': 'airbnb',
            'import_type': 'email',
            'import_id': booking_import.id,
        }

        _logger.info(f"🔍 PROCESSOR - booking_vals['rate'] avant création: {booking_vals['rate']}")

        booking_line = BookingLine.create(booking_vals)

        # Vérification après création
        _logger.info(f"🔍 PROCESSOR - booking_line.rate après création: {booking_line.rate}")

        if booking_line.rate == 0 and rate_xpf > 0:
            _logger.error(f"❌ PROBLÈME CRITIQUE: booking_line.rate = 0 alors que rate_xpf = {rate_xpf}")
            _logger.error("   → Vérifier la définition du champ 'rate' dans booking.import.line")
            _logger.error("   → Vérifier les règles de calcul/contraintes sur ce champ")

        _logger.info(
            f"✅ Réservation créée : {booking_line.booking_reference} - "
            f"{partner.name} - {property_type.name} - {booking_line.rate:.2f} XPF"
        )

        return booking_line

    # ============================================
    # MISE À JOUR LEAD CRM
    # ============================================

    def _update_lead(self, lead, booking_line, partner, company):
        """
        Met à jour le lead CRM
        Le revenu attendu reste en XPF (devise de la société)
        """
        _logger.info(f"🔍 PROCESSOR - Mise à jour lead {lead.id}:")
        _logger.info(f"  - booking_line.rate: {booking_line.rate}")

        lead.sudo().write({
            'partner_id': partner.id,
            'booking_line_id': booking_line.id,
            'stage_id': self.env.ref('os_airbnb_email_import.crm_stage_airbnb_confirmed').id,
            'expected_revenue': booking_line.rate,  # XPF, pas de conversion
        })

        _logger.info(f"  - lead.expected_revenue après write: {lead.expected_revenue}")
        _logger.info(f"✅ Lead {lead.id} mis à jour → stage 'Confirmé' (revenu: {booking_line.rate:.2f} XPF)")

    # ============================================
    # LIAISON PÉRIODES
    # ============================================

    def _link_to_periods(self, booking_line):
        """Lie la réservation aux vues mensuelles et trimestrielles"""
        if not booking_line.arrival_date or not booking_line.property_type_id:
            return

        year = booking_line.arrival_date.year
        month = booking_line.arrival_date.month

        # Création/liaison vue mensuelle
        booking_month = self.env['booking.month'].sudo().create_or_update_month(
            property_type_id=booking_line.property_type_id.id,
            year=year,
            month=month,
            company_id=booking_line.company_id.id
        )

        booking_line.sudo().write({'booking_month_id': booking_month.id})

        # Création/liaison déclaration trimestrielle
        booking_quarter = self.env['booking.quarter'].sudo().create_or_update_quarter(
            booking_line.property_type_id.id, year, month, booking_line.company_id.id
        )

        booking_line.sudo().write({'booking_quarter_id': booking_quarter.id})

        _logger.info(
            f"✅ Réservation liée : Mois {booking_month.display_name}, "
            f"Trimestre {booking_quarter.display_name}"
        )

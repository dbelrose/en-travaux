# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

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
        # 1. Créer ou récupérer le contact
        partner = self._create_or_get_partner(parsed_data, company)
        
        # 2. Trouver ou créer le logement
        property_type = self._find_or_create_property(parsed_data, company)
        
        # 3. Créer la réservation
        booking_line = self._create_booking_line(parsed_data, partner, property_type, company)
        
        # 4. Mettre à jour le lead CRM
        self._update_lead(lead, booking_line, partner)
        
        # 5. Lier aux vues mensuelles/trimestrielles
        self._link_to_periods(booking_line)
        
        return booking_line

    # ============================================
    # CRÉATION/RÉCUPÉRATION CONTACT
    # ============================================

    def _create_or_get_partner(self, data, company):
        """
        Crée ou récupère le contact client
        
        Recherche par :
        1. Nom + Prénom
        2. Si non trouvé, créer nouveau
        """
        Partner = self.env['res.partner'].sudo()
        
        firstname = data.get('first_name', 'Voyageur')
        lastname = data.get('last_name', 'Airbnb')
        
        # Recherche par nom complet
        partner = Partner.search([
            ('firstname', '=', firstname),
            ('lastname', '=', lastname),
            ('company_id', '=', company.id),
        ], limit=1)
        
        if partner:
            _logger.info(f"✅ Partner trouvé : {partner.name} (ID: {partner.id})")
            return partner
        
        # Création nouveau contact
        _logger.info(f"➕ Création nouveau partner : {firstname} {lastname}")
        
        # Récupération du pays
        country = False
        if data.get('country'):
            country = self.env['res.country'].search([
                '|',
                ('name', 'ilike', data['country']),
                ('code', 'ilike', data['country'][:2])
            ], limit=1)
        
        # Récupération catégorie Airbnb
        try:
            airbnb_category = self.env.ref('os_airbnb_pdf_import.res_partner_category_plateforme_airbnb')
        except:
            airbnb_category = False
        
        partner_vals = {
            'firstname': firstname,
            'lastname': lastname,
            'city': data.get('city', ''),
            'country_id': country.id if country else False,
            'company_id': company.id,
            'is_company': False,
            'customer_rank': 1,
            'category_id': [(6, 0, [airbnb_category.id])] if airbnb_category else [],
        }
        
        partner = Partner.create(partner_vals)
        _logger.info(f"✅ Partner créé : {partner.name} (ID: {partner.id})")
        
        return partner

    # ============================================
    # RECHERCHE/CRÉATION LOGEMENT
    # ============================================

    def _find_or_create_property(self, data, company):
        """
        Trouve ou crée le logement via description_sale
        
        Recherche :
        1. Exact match sur description_sale
        2. Recherche partielle par mots-clés
        3. Création si non trouvé
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
        """
        Extrait les mots-clés principaux pour la recherche
        
        Example: "DUPLEX 4 CHAMBRES, DERNIER ÉTAGE" → ["DUPLEX", "4 CHAMBRES", "DERNIER"]
        """
        # Nettoyage
        cleaned = property_name.upper().replace(',', ' ')
        
        # Extraction mots significatifs (> 3 lettres)
        words = [w for w in cleaned.split() if len(w) > 3]
        
        # Retourner les 3 premiers mots-clés
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
    # CRÉATION RÉSERVATION
    # ============================================

    def _create_booking_line(self, data, partner, property_type, company):
        """Crée la ligne de réservation"""
        BookingLine = self.env['booking.import.line'].sudo()
        
        # Conversion EUR → XPF
        rate_xpf = company.convert_eur_to_xpf(data.get('rate_eur', 0))
        commission_xpf = company.convert_eur_to_xpf(data.get('commission_eur', 0))
        
        _logger.info(
            f"💰 Conversion : {data.get('rate_eur', 0)} EUR → {rate_xpf:.2f} XPF "
            f"(commission: {commission_xpf:.2f} XPF)"
        )
        
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
        }
        
        booking_line = BookingLine.create(booking_vals)
        
        _logger.info(
            f"✅ Réservation créée : {booking_line.booking_reference} - "
            f"{partner.name} - {property_type.name}"
        )
        
        return booking_line

    # ============================================
    # MISE À JOUR LEAD CRM
    # ============================================

    def _update_lead(self, lead, booking_line, partner):
        """
        Met à jour le lead CRM :
        - Lie au partner
        - Lie à la réservation
        - Passe en stage "Confirmé"
        """
        lead.sudo().write({
            'partner_id': partner.id,
            'booking_line_id': booking_line.id,
            'stage_id': self.env.ref('os_airbnb_email_import.crm_stage_airbnb_confirmed').id,
        })
        
        _logger.info(f"✅ Lead {lead.id} mis à jour → stage 'Confirmé'")

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
            booking_line.property_type_id.id, year, month
        )
        
        booking_line.sudo().write({'booking_quarter_id': booking_quarter.id})
        
        _logger.info(
            f"✅ Réservation liée : Mois {booking_month.display_name}, "
            f"Trimestre {booking_quarter.display_name}"
        )

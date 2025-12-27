# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BookingImportLine(models.Model):
    _name = 'booking.import.line'
    _description = 'Ligne de réservation importée'
    _order = 'arrival_date desc, id desc'
    _rec_name = 'display_name'

    @api.onchange('arrival_date', 'departure_date')
    def _default_duration_nights(self):
        for record in self:
            if record.arrival_date and record.departure_date:
                delta = record.departure_date - record.arrival_date
                record.duration_nights = delta.days if delta.days > 0 else 0
            else:
                record.duration_nights = 0

    # Relation avec l'import parent
    import_id = fields.Many2one(
        'booking.import',
        string='Import',
        required=False,
        ondelete='cascade'
    )
    booking_month_id = fields.Many2one(
        'booking.month',
        string='Mois de réservation',
        ondelete='set null',
        index=True,
        help='Mois de réservation associé pour un accès rapide'
    )
    # Nom d'affichage
    display_name = fields.Char(
        string='Nom',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('partner_id', 'arrival_date', 'property_type_id')
    def _compute_display_name(self):
        for record in self:
            name_parts = []
            if record.partner_id:
                name_parts.append(record.partner_id.name)
            if record.arrival_date:
                name_parts.append(record.arrival_date.strftime('%d/%m/%Y'))
            if record.property_type_id:
                name_parts.append(f"({record.property_type_id.name})")
            record.display_name = ' - '.join(name_parts) if name_parts else f"Réservation {record.id}"


    # Informations client
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        required=True
    )
    booker_id = fields.Many2one(
        'res.partner',
        string='Réservateur'
    )

    concierge_partner_id = fields.Many2one(
        'res.partner',
        string='Concierge',
        compute='_get_concierge_partner_id',
        store=True
    )

    @api.depends('property_type_id')
    def _get_concierge_partner_id(self):
        for record in self:
            record.concierge_partner_id = False

            if not record.property_type_id or not record.property_type_id.company_id:
                continue

            # Récupérer le type de relation "Concierge" via external ID
            try:
                concierge_relation_base = self.env.ref('os_hospitality_managment.relation_type_concierge')
                # Rechercher le type de sélection correspondant (côté concierge -> propriété)
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('type_id', '=', concierge_relation_base.id),
                    ('is_inverse', '=', False)  # Concierge vers Société
                ], limit=1)

            except ValueError:
                # Fallback si l'external ID n'existe pas
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('name', 'ilike', 'Concierge')
                ], limit=1)

            if not concierge_relation_type:
                continue

            # Rechercher la relation où :
            # - other_partner_id correspond à la société de la propriété
            # - type_selection_id correspond au type "Concierge"
            relation = self.env['res.partner.relation.all'].search([
                ('other_partner_id', '=', record.property_type_id.company_id.partner_id.id),
                ('type_selection_id', '=', concierge_relation_type.id),
                ('active', '=', True)  # Seulement les relations actives
            ], limit=1)

            if relation:
                record.concierge_partner_id = relation.this_partner_id
            else:
                # Fallback : utiliser le partenaire de la société comme avant
                record.concierge_partner_id = record.property_type_id.company_id.partner_id

    # Informations propriété
    property_type_id = fields.Many2one(
        'product.template',
        string='Hébergement',
        help='Type de propriété réservé',
        required=True
)

    # Informations séjour
    arrival_date = fields.Date(
        string='🟢 Arrivée',
        required=True,
        help='Date d\'arrivée du client (inclusif)'
    )
    departure_date = fields.Date(
        string='🔴 Départ',
        required=True,
        help='Date de départ du client (exclusif)',
    )
    reservation_date = fields.Date(
        string='✅ Réservation',
        required=True,
        help='Date à laquelle la réservation a été effectuée'
    )
    duration_nights = fields.Integer(
        string='🌙 Nuitées',
        required=False,
        default=_default_duration_nights,
    )

    pax_nb = fields.Integer(
        string='👥 Personnes',
        required=True,
        default=1,
        help='Nombre total de personnes (adultes + enfants)',
        store=True
    )
    children = fields.Integer(
        string='👶 Enfants',
        default=0,
        help='Nombre d\'enfants de 12 ans ou moins',
        store=True
    )

    adults = fields.Integer(
        string='🧑 Adultes',
        compute='_compute_adults',
        store=True,
        help='Nombre d\'adultes (pax_nb - children)'
    )

    @api.depends('pax_nb', 'children')
    def _compute_adults(self):
        for record in self:
            record.adults = max((record.pax_nb or 0) - (record.children or 0), 0)

    # Références booking
    booking_reference = fields.Char(
        string='Référence Booking'
    )
    booking_id = fields.Char(
        string='ID Booking'
    )
    # Statuts
    payment_status = fields.Selection([
        ('Entièrement payée', 'Entièrement payée'),
        ('Prépaiement réglé', 'Prépaiement réglé'),
        ('Partiellement payée', 'Partiellement payée'),
        ('Non payée', 'Non payée'),
        ('Remboursée', 'Remboursée'),
    ],
        string='Statut paiement',
        default='Entièrement payée'
    )
    status = fields.Selection([
        ('ok', 'Confirmé'),
        ('cancelled', 'Annulé'),
        ('no_show', 'No-show'),
        ('modified', 'Modifié'),
    ],
        string='Statut',
        default='ok'
    )
    # Informations financières
    rate = fields.Monetary(
        string='➕ CA',
        currency_field='company_currency_id',
        help='Montant facturé au client',
        store=True
    )
    commission_amount = fields.Monetary(
        string='➖ Plateforme',
        currency_field='company_currency_id',
        help='Montant de la commission de la plateforme',
        store=True
    )
    commission_rate = fields.Float(
        string='% Plateforme',
        compute='_compute_commission_rate',
        help='Taux de commission de la plateforme',
        store=True
    )

    @api.depends('rate', 'commission_amount')
    def _compute_commission_rate(self):
        for record in self:
            if record.rate and record.rate > 0:
                record.commission_rate = (record.commission_amount / record.rate) * 100
            else:
                record.commission_rate = 0.0

    concierge_service_id = fields.Many2one(
        'product.product',
        string='Conciergerie',
        domain="[('default_code', '=', 'COMMISSION_CONCIERGE'), '|', ('company_id', '=', company_id), ('company_id', "
               "'=', False)]",
        default=lambda self: self.env['product.product'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE'),
            '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)
        ], limit=1),
        help='Produit/service utilisé pour calculer la commission du concierge'
    )

    inverse_concierge_commission_rate = fields.Float(
        string='% Inverse concierge',
        compute='_compute_inverse_concierge_commission_rate',
        help='Le taux de commission inverse du concierge (100% - taux de commission)',
        store=True
    )

    concierge_commission_rate = fields.Float(
        string='% Concierge',
        compute='_compute_concierge_commission_rate',
        help='Taux de commission du concierge (100% - taux de commission inverse)',
        store=True
    )

    @api.depends('inverse_concierge_commission_rate')
    def _compute_concierge_commission_rate(self):
        """Calcule le taux de commission concierge"""
        for record in self:
            record.concierge_commission_rate = 100 - record.inverse_concierge_commission_rate or 0.0

    base_concierge_commission = fields.Monetary(
        string='Base concierge',
        compute='_compute_base_concierge_commission',
        currency_field='company_currency_id',
        help='Base de calcul pour la commission du concierge (CA - Commission plateforme - Taxe de séjour)',
        store=True
    )

    @api.depends('rate', 'commission_amount', 'origin', 'company_id.hm_airbnb_vendor_concierge_commission',
                 'company_id.hm_booking_vendor_concierge_commission',
                 'company_id.hm_airbnb_customer_concierge_commission',
                 'company_id.hm_booking_customer_concierge_commission')
    def _compute_base_concierge_commission(self):
        for record in self:
            airbnb_vendor_ok = record.origin == 'airbnb' and record.company_id.hm_airbnb_vendor_concierge_commission
            booking_vendor_ok = record.origin == 'booking.com' \
                                and record.company_id.hm_booking_vendor_concierge_commission
            airbnb_customer_ok = record.origin == 'airbnb' and record.company_id.hm_airbnb_customer_concierge_commission
            booking_customer_ok = record.origin == 'booking.com' \
                                  and record.company_id.hm_booking_customer_concierge_commission

            rate = record.rate or 0.0
            commission = record.commission_amount or 0.0
            tax_amount = record.tax_amount or 0.0

            if airbnb_vendor_ok or airbnb_customer_ok or booking_vendor_ok or booking_customer_ok:
                record.base_concierge_commission = rate - commission - tax_amount
            else:
                record.base_concierge_commission = 0.0

    concierge_commission = fields.Monetary(
        string='➖ Concierge',
        compute='_compute_concierge_commission',
        currency_field='company_currency_id',
        help='Montant de la commission du concierge',
        store=True
    )

    @api.depends('base_concierge_commission', 'concierge_commission_rate')
    def _compute_concierge_commission(self):
        """Calcule la commission concierge en utilisant le discount du supplierinfo"""
        for record in self:
            record.concierge_commission = record.base_concierge_commission * record.concierge_commission_rate / 100

    # Nuitées calculées
    nights_adults = fields.Integer(
        string='Nuitées adultes',
        compute='_compute_nights_adults',
        store=True
    )

    @api.depends('duration_nights', 'adults')
    def _compute_nights_adults(self):
        for record in self:
            record.nights_adults = (record.duration_nights or 0) * (record.adults or 0)

    nights_children = fields.Integer(
        string='Nuitées enfants',
        compute='_compute_nights_children',
        store=True
    )

    @api.depends('duration_nights', 'children')
    def _compute_nights_children(self):
        for record in self:
            record.nights_children = (record.duration_nights or 0) * (record.children or 0)

    total_nights = fields.Integer(
        string='Total nuitées',
        compute='_compute_total_nights',
        store=True
    )

    @api.depends('nights_adults', 'nights_children')
    def _compute_total_nights(self):
        for record in self:
            record.total_nights = record.nights_adults + record.nights_children

    # TO
    tax_amount = fields.Monetary(
        string='➖ Mairie',
        compute='_compute_tax_amount',
        currency_field='company_currency_id',
        store=True
    )

    @api.depends('nights_adults')
    def _compute_tax_amount(self):
        # TODO: Adapter le calcul de la taxe de séjour selon les règles locales
        for record in self:
            record.tax_amount = record.nights_adults * 60.0

    # Métadonnées
    create_date = fields.Datetime(string='Date de création', readonly=True)
    write_date = fields.Datetime(string='Dernière modification', readonly=True)

    # Société
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        related='import_id.company_id',
        store=True
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        related='company_id.currency_id'
    )

    origin = fields.Selection([
        ('booking.com', 'Booking.com'),
        ('other', 'Autre'),
    ],
        string='Origine',
        default='booking.com'
    )

    import_type = fields.Selection([
        ('file', 'XLS'),
        ('manual', 'Saisie manuelle')
    ],
        string='Format',
        default='file'
    )

    def _get_concierge_partner(self):
        """Récupère le partenaire concierge pour cette ligne de réservation"""
        if not self.property_type_id or not self.property_type_id.company_id:
            return False

        # Récupérer le type de relation "Concierge" via external ID
        try:
            concierge_relation_base = self.env.ref('os_hospitality_managment.relation_type_concierge')
            # Rechercher le type de sélection correspondant (côté concierge -> propriété)
            concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                ('type_id', '=', concierge_relation_base.id),
                ('is_inverse', '=', False)  # Concierge vers Société
            ], limit=1)
        except ValueError:
            # Fallback si l'external ID n'existe pas
            concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                ('name', 'ilike', 'Concierge')
            ], limit=1)

        if not concierge_relation_type:
            return False

        # Rechercher la relation
        relation = self.env['res.partner.relation.all'].search([
            ('other_partner_id', '=', self.property_type_id.company_id.partner_id.id),
            ('type_selection_id', '=', concierge_relation_type.id),
            ('active', '=', True)
        ], limit=1)

        if relation:
            return relation.this_partner_id
        else:
            # Fallback : utiliser le partenaire de la société
            return self.property_type_id.company_id.partner_id

    @api.depends('pax_nb', 'children')
    def _compute_adults(self):
        for record in self:
            record.adults = max((record.pax_nb or 0) - (record.children or 0), 0)

    @api.depends('duration_nights', 'adults', 'children')
    def _compute_nights(self):
        for record in self:
            record.nights_adults = (record.duration_nights or 0) * (record.adults or 0)
            record.nights_children = (record.duration_nights or 0) * (record.children or 0)
            record.total_nights = record.nights_adults + record.nights_children

    @api.depends('company_id', 'concierge_partner_id')
    def _compute_inverse_concierge_commission_rate(self):
        """Calcule le taux de commission inverse concierge en utilisant le discount du supplierinfo"""
        for record in self:
            taux = 0.0

            # Rechercher le produit COMMISSION_CONCIERGE
            concierge_service = record.env['product.product'].search([
                ('default_code', '=', 'COMMISSION_CONCIERGE'),
                '|', ('company_id', '=', record.company_id.id), ('company_id', '=', False)
            ], limit=1)

            if concierge_service:
                # Trouver le partenaire concierge pour cette propriété
                concierge_partner = record.concierge_partner_id

                if concierge_partner:
                    # Rechercher l'info fournisseur correspondante
                    supplier_info = concierge_service.seller_ids.filtered(
                        lambda s: s.partner_id == concierge_partner
                    )

                    if supplier_info:
                        taux = supplier_info[0].discount
                    else:
                        # Fallback : utiliser le prix du produit comme pourcentage
                        taux = 100 - concierge_service.list_price

            record.inverse_concierge_commission_rate = taux

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Met à jour le booker par défaut quand le client change"""
        if self.partner_id and not self.booker_id:
            self.booker_id = self.partner_id

    @api.onchange('pax_nb')
    def _onchange_pax_nb(self):
        """Valide que le nombre d'enfants ne dépasse pas le nombre total de personnes"""
        if self.children and self.pax_nb and self.children > self.pax_nb:
            self.children = self.pax_nb

    @api.constrains('duration_nights', 'pax_nb')
    def _check_positive_values(self):
        """Vérifie que les valeurs sont positives"""
        for record in self:
            if record.duration_nights <= 0:
                raise ValueError("La durée du séjour doit être positive")
            if record.pax_nb <= 0:
                raise ValueError("Le nombre de personnes doit être positif")

    @api.constrains('children', 'pax_nb')
    def _check_children_count(self):
        """Vérifie que le nombre d'enfants ne dépasse pas le nombre total"""
        for record in self:
            if record.children > record.pax_nb:
                raise ValueError("Le nombre d'enfants ne peut pas dépasser le nombre total de personnes")

    def name_get(self):
        """Retourne un nom lisible pour les lignes"""
        result = []
        for record in self:
            result.append((record.id, record.display_name))
        return result

    @api.model_create_multi
    def create(self, vals_list):
        """Surcharge create pour validation et mise à jour automatique"""
        records = super().create(vals_list)

        # Mettre à jour les déclarations trimestrielles et vues mensuelles
        for record in records:
            if record.arrival_date and record.property_type_id:
                year = record.arrival_date.year
                month = record.arrival_date.month

                # Mettre à jour la déclaration trimestrielle
                self.env['booking.quarter'].create_or_update_quarter(
                    record.property_type_id.id, year, month
                )

                # Mettre à jour la vue mensuelle
                self.env['booking.month'].create_or_update_month(
                    property_type_id=record.property_type_id.id,
                    year=year,
                    month=month,
                    company_id=record.company_id.id
                )

        return records

    def write(self, vals):
        """Surcharge write pour validation et mise à jour automatique"""
        # Sauvegarder les anciennes valeurs pour les mises à jour
        old_values = []
        for record in self:
            old_values.append({
                'id': record.id,
                'arrival_date': record.arrival_date,
                'property_type_id': record.property_type_id.id if record.property_type_id else False
            })

        result = super().write(vals)

        # Mettre à jour les déclarations et vues concernées
        periods_to_update = set()

        for record, old_val in zip(self, old_values):
            # Ajouter l'ancienne période si elle a changé
            if old_val['arrival_date'] and old_val['property_type_id']:
                old_year = old_val['arrival_date'].year
                old_month = old_val['arrival_date'].month
                periods_to_update.add((old_val['property_type_id'], old_year, old_month))

            # Ajouter la nouvelle période
            if record.arrival_date and record.property_type_id:
                new_year = record.arrival_date.year
                new_month = record.arrival_date.month
                periods_to_update.add((record.property_type_id.id, new_year, new_month))

        # Effectuer les mises à jour
        for property_type_id, year, month in periods_to_update:
            self.env['booking.quarter'].create_or_update_quarter(property_type_id, year, month)
            self.env['booking.month'].create_or_update_month(
                property_type_id=property_type_id,
                year=year,
                month=month
            )

        return result

    def unlink(self):
        """Surcharge unlink pour mise à jour automatique"""
        # Sauvegarder les périodes concernées avant suppression
        periods_to_update = set()
        for record in self:
            if record.arrival_date and record.property_type_id:
                year = record.arrival_date.year
                month = record.arrival_date.month
                periods_to_update.add((record.property_type_id.id, year, month))

        result = super().unlink()

        # Mettre à jour les déclarations et vues
        for property_type_id, year, month in periods_to_update:
            self.env['booking.quarter'].create_or_update_quarter(property_type_id, year, month)
            self.env['booking.month'].create_or_update_month(
                property_type_id=property_type_id,
                year=year,
                month=month
            )

        return result

    def action_edit(self):
        """Action pour modifier une réservation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Modifier la réservation',
            'res_model': 'booking.import.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_import_id': self.import_id.id,
                'default_partner_id': self.partner_id.id,
                'default_booker_id': self.booker_id.id,
                'default_arrival_date': self.arrival_date,
                'default_duration_nights': self.duration_nights,
                'default_pax_nb': self.pax_nb,
                'default_children': self.children,
                'default_payment_status': self.payment_status,
                'default_status': self.status,
                'default_rate': self.rate,
                'default_commission_amount': self.commission_amount,
                'default_booking_reference': self.booking_reference,
                'line_to_edit': self.id,
            }
        }

    def action_duplicate(self):
        """Action pour dupliquer une réservation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dupliquer la réservation',
            'res_model': 'booking.import.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_import_id': self.import_id.id,
                'default_partner_id': self.partner_id.id,
                'default_booker_id': self.booker_id.id,
                'default_arrival_date': self.arrival_date,
                'default_departure_date': self.departure_date,
                'default_reservation_date': self.reservation_date,
                'default_duration_nights': self.duration_nights,
                'default_pax_nb': self.pax_nb,
                'default_children': self.children,
                'default_payment_status': self.payment_status,
                'default_status': self.status,
                'default_rate': self.rate,
                'default_commission_amount': self.commission_amount,
                'default_booking_reference': self.booking_reference,
            }
        }

    def action_cancel_reservation(self):
        """Annule une réservation"""
        self.ensure_one()
        self.status = 'cancelled'
        return True

    def action_mark_no_show(self):
        """Marque une réservation comme no-show"""
        self.ensure_one()
        self.status = 'no_show'
        return True

    def action_view_quarter(self):
        """Affiche la déclaration trimestrielle correspondante"""
        self.ensure_one()
        if not self.arrival_date or not self.property_type_id:
            return False

        year = self.arrival_date.year
        month = self.arrival_date.month
        quarter = ((month - 1) // 3) + 1

        quarter_record = self.env['booking.quarter'].search([
            ('year', '=', year),
            ('quarter', '=', quarter),
            ('property_type_id', '=', self.property_type_id.id)
        ], limit=1)

        if quarter_record:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Déclaration trimestrielle',
                'res_model': 'booking.quarter',
                'view_mode': 'form',
                'res_id': quarter_record.id,
                'target': 'current',
            }
        return False

    def action_view_month(self):
        """Affiche la vue mensuelle correspondante"""
        self.ensure_one()
        if not self.arrival_date or not self.property_type_id:
            return False

        year = self.arrival_date.year
        month = self.arrival_date.month

        month_record = self.env['booking.month'].search([
            ('year', '=', year),
            ('month', '=', month),
            ('property_type_id', '=', self.property_type_id.id)
        ], limit=1)

        if month_record:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Vue mensuelle',
                'res_model': 'booking.month',
                'view_mode': 'form',
                'res_id': month_record.id,
                'target': 'current',
            }
        return False

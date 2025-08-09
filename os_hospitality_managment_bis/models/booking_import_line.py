# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BookingImportLine(models.Model):
    _name = 'booking.import.line'
    _description = 'Ligne de réservation importée'
    _order = 'arrival_date desc, id desc'
    _rec_name = 'display_name'

    # Relation avec l'import parent
    import_id = fields.Many2one('booking.import', string='Import', required=True, ondelete='cascade')

    # Nom d'affichage
    display_name = fields.Char(string='Nom', compute='_compute_display_name', store=True)

    # Informations client
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    booker_id = fields.Many2one('res.partner', string='Réservateur')

    # Informations propriété
    property_type_id = fields.Many2one('product.template', string='Type d\'hébergement', required=True)

    # Informations séjour
    arrival_date = fields.Date(string='Date d\'arrivée', required=True)
    departure_date = fields.Date(string='Date de départ', compute='_compute_departure_date', store=True)
    duration_nights = fields.Integer(string='Durée (nuits)', required=True, default=1)
    pax_nb = fields.Integer(string='Nombre de personnes', required=True, default=1)
    children = fields.Integer(string='Nombre d\'enfants (≤12 ans)', default=0)
    adults = fields.Integer(string='Nombre d\'adultes', compute='_compute_adults', store=True)

    # Références booking
    booking_reference = fields.Char(string='Référence Booking')
    booking_id = fields.Char(string='ID Booking')

    # Statuts
    payment_status = fields.Selection([
        ('Entièrement payée', 'Entièrement payée'),
        ('Prépaiement réglé', 'Prépaiement réglé'),
        ('Partiellement payée', 'Partiellement payée'),
        ('Non payée', 'Non payée'),
        ('Remboursée', 'Remboursée'),
    ], string='Statut paiement', default='Entièrement payée')

    status = fields.Selection([
        ('ok', 'Confirmé'),
        ('cancelled', 'Annulé'),
        ('no_show', 'No-show'),
        ('modified', 'Modifié'),
    ], string='Statut', default='ok')

    # Informations financières
    rate = fields.Float(string='Tarif (XPF)', digits='Product Price')
    commission_amount = fields.Float(string='Commission (XPF)', digits='Product Price')
    commission_rate = fields.Float(string='Taux commission (%)', compute='_compute_commission_rate', store=True)

    # Nuitées calculées
    nights_adults = fields.Integer(string='Nuitées adultes', compute='_compute_nights', store=True)
    nights_children = fields.Integer(string='Nuitées enfants', compute='_compute_nights', store=True)
    total_nights = fields.Integer(string='Total nuitées', compute='_compute_nights', store=True)

    # Montant taxe de séjour
    tax_amount = fields.Float(string='Taxe de séjour (XPF)', compute='_compute_tax_amount', store=True)

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

    @api.depends('arrival_date', 'duration_nights')
    def _compute_departure_date(self):
        for record in self:
            if record.arrival_date and record.duration_nights:
                record.departure_date = fields.Date.add(record.arrival_date, days=record.duration_nights)
            else:
                record.departure_date = False

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

    @api.depends('nights_adults')
    def _compute_tax_amount(self):
        """Calcule le montant de la taxe de séjour (60 XPF par nuitée adulte)"""
        for record in self:
            record.tax_amount = record.nights_adults * 60.0

    @api.depends('rate', 'commission_amount')
    def _compute_commission_rate(self):
        for record in self:
            if record.rate and record.rate > 0:
                record.commission_rate = (record.commission_amount / record.rate) * 100
            else:
                record.commission_rate = 0.0

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
                    record.property_type_id.id, year, month
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
            self.env['booking.month'].create_or_update_month(property_type_id, year, month)

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
            self.env['booking.month'].create_or_update_month(property_type_id, year, month)

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

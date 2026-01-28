# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)


class BookingReservationWizard(models.TransientModel):
    _name = 'booking.reservation.wizard'
    _description = 'Assistant pour ajouter/modifier une réservation'

    # Contexte
    import_id = fields.Many2one('booking.import', string='Import')
    line_id = fields.Many2one('booking.import.line', string='Réservation à modifier')
    edit_mode = fields.Boolean(string='Mode édition', default=False)

    # Informations client
    partner_id = fields.Many2one('res.partner', string='Client')
    create_new_partner = fields.Boolean(string='Créer un nouveau client')
    partner_name = fields.Char(string='Nom du client')
    partner_phone = fields.Char(string='Téléphone')
    partner_country_id = fields.Many2one('res.country', string='Pays')
    booker_id = fields.Many2one('res.partner', string='Réservateur')

    # Informations réservation
    property_type_id = fields.Many2one('product.template', string='Type d\'hébergement', required=True)
    arrival_date = fields.Date(string='Date d\'arrivée', required=True)
    duration_nights = fields.Integer(string='Durée (nuits)', required=True, default=1)
    pax_nb = fields.Integer(string='Nombre de personnes', required=True, default=1)
    children = fields.Integer(string='Enfants (≤12 ans)', default=0)

    # Informations Booking
    booking_reference = fields.Char(string='Référence Booking')
    payment_status = fields.Selection([
        ('paid', 'Entièrement payée'),
        ('partial', 'Partiellement payée'),
        ('unpaid', 'Non payée'),
        ('refunded', 'Remboursée'),
    ], string='Statut paiement', default='paid')
    status = fields.Selection([
        ('ok', 'Confirmée'),
        ('cancelled', 'Annulée'),
        ('no_show', 'No-show'),
    ], string='Statut', default='ok')

    # Informations financières
    rate = fields.Float(string='Tarif (XPF)')
    commission_amount = fields.Float(string='Commission (XPF)')

    # Source
    source = fields.Selection([
        ('booking', 'Booking.com'),
        ('airbnb', 'Airbnb'),
        ('manual', 'Saisie manuelle'),
        ('other', 'Autre'),
    ], string='Source', default='manual')

    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut"""
        res = super().default_get(fields_list)

        # Si on est en mode édition, récupérer les valeurs de la ligne
        if self.env.context.get('edit_mode') and self.env.context.get('default_line_id'):
            line = self.env['booking.import.line'].browse(self.env.context['default_line_id'])
            if line.exists():
                res.update({
                    'line_id': line.id,
                    'edit_mode': True,
                    'import_id': line.import_id.id,
                    'partner_id': line.partner_id.id,
                    'booker_id': line.booker_id.id,
                    'property_type_id': line.property_type_id.id,
                    'arrival_date': line.arrival_date,
                    'duration_nights': line.duration_nights,
                    'pax_nb': line.pax_nb,
                    'children': line.children,
                    'booking_reference': line.booking_reference,
                    'payment_status': line.payment_status,
                    'status': line.status,
                    'rate': line.rate,
                    'commission_amount': line.commission_amount,
                    'source': line.source,
                })

        return res

    @api.onchange('create_new_partner')
    def _onchange_create_new_partner(self):
        """Reset des champs si on change le mode"""
        if self.create_new_partner:
            self.partner_id = False
        else:
            self.partner_name = False
            self.partner_phone = False
            self.partner_country_id = False

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Met à jour le booker par défaut"""
        if self.partner_id and not self.booker_id:
            self.booker_id = self.partner_id

    @api.onchange('pax_nb')
    def _onchange_pax_nb(self):
        """Validation du nombre de personnes"""
        if self.pax_nb and self.children and self.children > self.pax_nb:
            self.children = self.pax_nb

    def action_save(self):
        """Sauvegarde la réservation"""
        self.ensure_one()

        # Créer le client si nécessaire
        if self.create_new_partner:
            if not self.partner_name:
                raise UserError("Le nom du client est requis.")

            partner = self.env['res.partner'].search([('name', '=', self.partner_name)], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({
                    'name': self.partner_name,
                    'phone': self.partner_phone,
                    'country_id': self.partner_country_id.id if self.partner_country_id else False,
                    'company_id': self.env.user.company_id.id,
                    'customer_rank': 1,
                    'category_id': [
                        (6, 0, self.env.ref('os_hospitality_managment.res_partner_category_plateforme_booking').ids)]
                })
        else:
            partner = self.partner_id

        if not partner:
            raise UserError("Veuillez sélectionner ou créer un client.")

        # Préparer les valeurs
        vals = {
            'partner_id': partner.id,
            'booker_id': self.booker_id.id if self.booker_id else partner.id,
            'property_type_id': self.property_type_id.id,
            'arrival_date': self.arrival_date,
            'duration_nights': self.duration_nights,
            'pax_nb': self.pax_nb,
            'children': self.children,
            'booking_reference': self.booking_reference,
            'payment_status': self.payment_status,
            'status': self.status,
            'rate': self.rate,
            'commission_amount': self.commission_amount,
            'source': self.source,
        }

        if self.edit_mode and self.line_id:
            # Modification
            self.line_id.write(vals)
            message = 'Réservation modifiée avec succès.'
        else:
            # Création
            _logger.info(f"partner.name : {partner.name}")
            _logger.info(f"property_type_id.name : {self.property_type_id.name}")
            vals.update({
                'import_id': self.import_id.id,
                'external_id': f"manual_{self.arrival_date.strftime('%Y%m%d')}_{partner.name.replace(' ', '_')}_{self.property_type_id.name.replace(' ', '_')}",
            })
            self.env['booking.import.line'].create(vals)
            message = 'Réservation ajoutée avec succès.'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sauvegarde réussie',
                'message': message,
                'type': 'success',
            }
        }

    def action_cancel(self):
        """Annule le wizard"""
        return {'type': 'ir.actions.act_window_close'}

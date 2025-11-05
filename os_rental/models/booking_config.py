from odoo import models, fields


class BookingConfig(models.Model):
    _name = 'booking.config'
    _description = 'Configuration des Réservations'

    name = fields.Char(string='Nom', default='Configuration Réservation', required=True)
    billetweb_event_id = fields.Char(string='Billetweb Event ID', required=True, default='1150478')
    billetweb_ticket_id = fields.Char(string='Billetweb Ticket ID', required=True, default='5806545')
    billetweb_api_key = fields.Char(string='Billetweb API Key', required=True)
    cgv_url = fields.Char(string='URL CGV', default='https://www.billetweb.fr/files//terms/1162762.pdf?v=1729033372')

    min_nights = fields.Integer(string='Nombre minimum de nuits', default=2)
    max_months = fields.Integer(string='Durée maximum (mois)', default=3)

    weekly_discount = fields.Float(string='Réduction hebdomadaire (%)', default=10.0)
    weekly_nights = fields.Integer(string='Nuits pour réduction hebdo', default=7)

    monthly_discount = fields.Float(string='Réduction mensuelle (%)', default=20.0)
    monthly_nights = fields.Integer(string='Nuits pour réduction mensuelle', default=30)

    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('unique_active', 'CHECK(1=1)', 'Une seule configuration peut être active')
    ]

    def get_config(self):
        return self.search([('active', '=', True)], limit=1)

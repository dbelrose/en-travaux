from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Identifiants Billetweb
    billetweb_user_id = fields.Char(
        string='Billetweb User ID',
        config_parameter='booking.billetweb_user_id',
        help="Votre ID utilisateur Billetweb"
    )
    billetweb_api_key = fields.Char(
        string='Billetweb API Key',
        config_parameter='booking.billetweb_api_key',
        help="Clé API Billetweb. Format possible: 'user:key' ou uniquement la clé"
    )
    billetweb_event_id = fields.Char(
        string='Billetweb Event ID',
        config_parameter='booking.billetweb_event_id',
        default='1150478',
        help="ID de l’événement sur Billetweb"
    )
    billetweb_ticket_id = fields.Char(
        string='Billetweb Ticket ID',
        config_parameter='booking.billetweb_ticket_id',
        default='5806545',
        help="ID du tarif (ticket) sur Billetweb"
    )

    # Autres paramètres réservation
    cgv_url = fields.Char(
        string='URL CGV',
        config_parameter='booking.cgv_url',
        help="Lien vers les Conditions Générales de Vente"
    )
    min_nights = fields.Integer(
        string='Nombre minimum de nuits',
        config_parameter='booking.min_nights',
        default=2
    )
    max_months = fields.Integer(
        string='Durée maximum (mois)',
        config_parameter='booking.max_months',
        default=3
    )
    weekly_discount = fields.Float(
        string='Réduction hebdomadaire (%)',
        config_parameter='booking.weekly_discount',
        default=10.0
    )
    weekly_nights = fields.Integer(
        string='Nuits pour réduction hebdo',
        config_parameter='booking.weekly_nights',
        default=7
    )
    monthly_discount = fields.Float(
        string='Réduction mensuelle (%)',
        config_parameter='booking.monthly_discount',
        default=20.0
    )
    monthly_nights = fields.Integer(
        string='Nuits pour réduction mensuelle',
        config_parameter='booking.monthly_nights',
        default=30
    )

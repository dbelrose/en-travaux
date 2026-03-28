from odoo import models, fields, api


class BookingConfig(models.Model):
    _name = 'booking.config'
    _description = 'Configuration des Réservations'

    name = fields.Char(string='Nom',
                       default='Configuration Réservation',
                       store=True,
                       required=True)

    # Configuration Billetweb - Format: user:key ou juste key
    billetweb_user_id = fields.Char(string='Billetweb User ID',
                                    store=True,
                                    required=True,
                                    help="Votre ID utilisateur Billetweb")
    billetweb_api_key = fields.Char(string='Billetweb API Key',
                                    store=True,
                                    required=True,
                                    help="Votre clé API Billetweb. Format: 'user:key' ou juste la clé")
    billetweb_event_id = fields.Char(string='Billetweb Event ID',
                                     store=True,
                                     required=True,
                                     default='1150478',
                                     help="ID de l'événement sur Billetweb")
    billetweb_ticket_id = fields.Char(string='Billetweb Ticket ID',
                                        store=True,
                                      required=True,
                                      default='5806545',
                                      help="ID du tarif sur Billetweb")
    cgv_url = fields.Char(string='URL CGV',
                          store=True,
                          default='https://www.billetweb.fr/files//terms/1162762.pdf?v=1729033372')

    min_nights = fields.Integer(string='Nombre minimum de nuits',
                                store=True,
                                default=2)
    max_months = fields.Integer(string='Durée maximum (mois)',
                                store=True,
                                default=3)

    weekly_discount = fields.Float(string='Réduction hebdomadaire (%)',
                                   store=True,
                                   default=10.0)
    weekly_nights = fields.Integer(string='Nuits pour réduction hebdo',
                                   store=True,
                                   default=7)

    monthly_discount = fields.Float(string='Réduction mensuelle (%)',
                                    store=True,
                                    default=20.0)
    monthly_nights = fields.Integer(string='Nuits pour réduction mensuelle',
                                    store=True,
                                    default=30)

    active = fields.Boolean(string='Actif',
                            store=True,
                            default=True)

    _sql_constraints = [
        ('unique_active', 'CHECK(1=1)', 'Une seule configuration peut être active')
    ]

    @api.model
    def get_config(self):
        return self.search([('active', '=', True)], limit=1)


    def _get_booking_param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param(f'booking.{key}', default)

    def get_api_credentials(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('booking.billetweb_api_key') or ''
        user_id = ICP.get_param('booking.billetweb_user_id') or ''
        if ':' in api_key:
            user, key = api_key.split(':', 1)
            return user, key
        return (user_id or None), api_key

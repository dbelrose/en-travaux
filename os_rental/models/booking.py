from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class BookingReservation(models.Model):
    _name = 'booking.reservation'
    _description = 'Réservation de Logement'
    _order = 'create_date desc'

    name = fields.Char(string='Référence', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    product_id = fields.Many2one('product.template', string='Logement', required=True,
                                 domain=[('is_accommodation', '=', True)])

    start_date = fields.Date(string='Date début', required=True)
    end_date = fields.Date(string='Date fin', required=True)
    nights = fields.Integer(string='Nombre de nuits', compute='_compute_nights', store=True)

    nightly_rate = fields.Float(string='Tarif/nuit', required=True)
    subtotal = fields.Float(string='Sous-total', compute='_compute_amounts', store=True)
    discount_percent = fields.Float(string='Réduction (%)', compute='_compute_amounts', store=True)
    discount_amount = fields.Float(string='Montant réduction', compute='_compute_amounts', store=True)
    total_amount = fields.Float(string='Montant total', compute='_compute_amounts', store=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('payment_sent', 'Lien de paiement envoyé'),
        ('paid', 'Payé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', required=True)

    billetweb_order_id = fields.Char(string='ID Commande Billetweb')
    billetweb_payment_url = fields.Char(string='URL Paiement Billetweb')

    notes = fields.Text(string='Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('booking.reservation') or 'New'
        return super().create(vals)

    @api.depends('start_date', 'end_date')
    def _compute_nights(self):
        for booking in self:
            if booking.start_date and booking.end_date:
                delta = booking.end_date - booking.start_date
                booking.nights = delta.days
            else:
                booking.nights = 0

    @api.depends('nights', 'nightly_rate')
    def _compute_amounts(self):
        config = self.env['booking.config'].get_config()
        for booking in self:
            booking.subtotal = booking.nights * booking.nightly_rate

            # Calcul de la réduction
            discount = 0.0
            if config:
                if booking.nights >= config.monthly_nights:
                    discount = config.monthly_discount
                elif booking.nights >= config.weekly_nights:
                    discount = config.weekly_discount

            booking.discount_percent = discount
            booking.discount_amount = booking.subtotal * (discount / 100)
            booking.total_amount = booking.subtotal - booking.discount_amount

    @api.constrains('start_date', 'end_date', 'product_id')
    def _check_dates_and_availability(self):
        config = self.env['booking.config'].get_config()
        for booking in self:
            if booking.start_date >= booking.end_date:
                raise ValidationError(_('La date de fin doit être après la date de début.'))

            if config:
                # Vérifier le minimum de nuits
                if booking.nights < config.min_nights:
                    raise ValidationError(_('Le minimum est de %d nuits.') % config.min_nights)

                # Vérifier le maximum
                max_days = config.max_months * 30
                if booking.nights > max_days:
                    raise ValidationError(_('La durée maximum est de %d mois.') % config.max_months)

            # Vérifier la disponibilité
            if not booking.product_id.get_availability(booking.start_date, booking.end_date):
                raise ValidationError(_('Ce logement n\'est pas disponible pour ces dates.'))

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.nightly_rate = self.product_id.nightly_rate

    def action_confirm(self):
        """Confirme la réservation et lance la création de commande Billetweb"""
        self.ensure_one()
        self.state = 'confirmed'
        self.with_delay()._create_billetweb_order()
        return True

    def _create_billetweb_order(self):
        """Crée une commande sur Billetweb via l'API"""
        self.ensure_one()
        config = self.env['booking.config'].get_config()

        if not config:
            raise ValidationError(_('Configuration Billetweb manquante.'))

        company = self.env.company
        logo_url = False
        if company.partner_id.image_1920:
            # En production, utiliser une URL publique pour le logo
            logo_url = f'/web/image/res.partner/{company.partner_id.id}/image_1920'

        # Données pour l'API Billetweb
        payload = {
            'event': config.billetweb_event_id,
            'ticket': config.billetweb_ticket_id,
            'firstname': self.partner_id.name.split()[0] if self.partner_id.name else '',
            'lastname': ' '.join(self.partner_id.name.split()[1:]) if len(self.partner_id.name.split()) > 1 else '',
            'email': self.partner_id.email,
            'language': self.partner_id.lang or 'fr',
            'price': self.total_amount,
            'reference': self.name,
            'custom_fields': json.dumps({
                'logement': self.product_id.name,
                'date_debut': str(self.start_date),
                'date_fin': str(self.end_date),
                'nuits': self.nights,
            }),
        }

        if logo_url:
            payload['logo'] = logo_url

        try:
            response = requests.post(
                'https://www.billetweb.fr/bo/api.php',
                data=payload,
                headers={'Authorization': f'Bearer {config.billetweb_api_key}'},
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if result.get('success'):
                self.billetweb_order_id = result.get('order_id')
                self.billetweb_payment_url = result.get('payment_url')
                self._send_payment_email()
                self.state = 'payment_sent'
            else:
                error_msg = result.get('error', 'Erreur inconnue')
                _logger.error(f'Erreur Billetweb: {error_msg}')
                raise ValidationError(_('Erreur lors de la création de la commande: %s') % error_msg)

        except requests.exceptions.RequestException as e:
            _logger.error(f'Erreur API Billetweb: {str(e)}')
            raise ValidationError(_('Erreur de connexion à Billetweb: %s') % str(e))

    def _send_payment_email(self):
        """Envoie l'email avec le lien de paiement"""
        self.ensure_one()
        template = self.env.ref('booking_billetweb.email_template_payment_link')
        template.send_mail(self.id, force_send=True)

    def action_cancel(self):
        self.state = 'cancelled'

    def action_mark_paid(self):
        """Marque la réservation comme payée (webhook Billetweb)"""
        self.state = 'paid'

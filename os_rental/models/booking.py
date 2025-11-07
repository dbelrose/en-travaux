# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class BookingReservation(models.Model):
    """
    Modèle de réservation simple, intégrant :
      - calcul des montants (réductions hebdo/mensuelles),
      - contrôles de cohérence des dates et disponibilité,
      - création d'une commande Billetweb via l'API,
      - lecture des paramètres depuis ir.config_parameter (écrits via res.config.settings).
    """
    _name = 'booking.reservation'
    _description = 'Réservation de Logement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ---------------------------
    # Champs principaux
    # ---------------------------
    name = fields.Char(string='Référence', required=True, copy=False,
                       readonly=True, default='New', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    product_id = fields.Many2one(
        'product.template',
        string='Logement',
        required=True,
        domain=[('is_accommodation', '=', True)]
    )

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
    ], string='État', default='draft', required=True, tracking=True)

    billetweb_order_id = fields.Char(string='ID Commande Billetweb')
    billetweb_payment_url = fields.Char(string='URL Paiement Billetweb')

    notes = fields.Text(string='Notes')

    # ---------------------------
    # Séquences & basiques
    # ---------------------------
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('booking.reservation') or 'New'
        return super().create(vals)

    # ---------------------------
    # Computes
    # ---------------------------
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
        """
        Calcul des montants à partir des paramètres globaux (hebdo/mensuel).
        Note : un changement de paramètres n'entraîne pas un recompute automatique
        sur les réservations existantes (pas de @depends sur ir.config_parameter).
        """
        settings = self._get_settings()
        for booking in self:
            booking.subtotal = booking.nights * booking.nightly_rate

            # Détermination du pourcentage de remise
            discount = 0.0
            if booking.nights >= settings['monthly_nights']:
                discount = settings['monthly_discount']
            elif booking.nights >= settings['weekly_nights']:
                discount = settings['weekly_discount']

            booking.discount_percent = discount
            booking.discount_amount = booking.subtotal * (discount / 100.0)
            booking.total_amount = booking.subtotal - booking.discount_amount

    # ---------------------------
    # Contraintes métier
    # ---------------------------
    @api.constrains('start_date', 'end_date', 'product_id')
    def _check_dates_and_availability(self):
        settings = self._get_settings()
        for booking in self:
            if not booking.start_date or not booking.end_date:
                continue

            if booking.start_date >= booking.end_date:
                raise ValidationError(_('La date de fin doit être après la date de début.'))

            # Minimum de nuits
            if booking.nights < settings['min_nights']:
                raise ValidationError(_('Le minimum est de %d nuits.') % settings['min_nights'])

            # Maximum (mois convertis approximativement en jours)
            max_days = settings['max_months'] * 30
            if booking.nights > max_days:
                raise ValidationError(_('La durée maximum est de %d mois.') % settings['max_months'])

            # Disponibilité du logement (exclut la réservation en cours et les états non bloquants)
            if booking.state == 'cancelled':
                continue

            overlapping = self.env['booking.reservation'].search([
                ('product_id', '=', booking.product_id.id),
                ('state', 'in', ['confirmed', 'payment_sent', 'paid']),  # exclut draft & cancelled
                ('id', '!=', booking.id),
                ('start_date', '<', booking.end_date),
                ('end_date', '>', booking.start_date),
            ])
            if overlapping:
                raise ValidationError(
                    _("Ce logement n'est pas disponible pour ces dates.\n"
                      "Réservations en conflit: %s") % ', '.join(overlapping.mapped('name'))
                )

    # ---------------------------
    # Onchange
    # ---------------------------
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # suppose que product.template possède le champ nightly_rate
            self.nightly_rate = self.product_id.nightly_rate

    # ---------------------------
    # Helpers Paramètres (ir.config_parameter)
    # ---------------------------
    def _get_booking_param(self, key, default=None):
        """Lecture centralisée (sudo) dans ir.config_parameter sous préfixe 'booking.'"""
        ICP = self.env['ir.config_parameter'].sudo()
        return ICP.get_param(f'booking.{key}', default)

    @staticmethod
    def _to_int(val, default=0):
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(val, default=0.0):
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    def _get_settings(self):
        """
        Rassemble toutes les clés utiles en un seul dict, avec cast des types
        et valeurs par défaut alignées sur les anciens defaults.
        """
        get = self._get_booking_param
        return {
            # Identifiants Billetweb
            'billetweb_user_id': get('billetweb_user_id') or None,
            'billetweb_api_key': get('billetweb_api_key') or '',
            'billetweb_event_id': get('billetweb_event_id') or '',
            'billetweb_ticket_id': get('billetweb_ticket_id') or '',
            'cgv_url': get('cgv_url') or '',
            # Règles
            'min_nights': self._to_int(get('min_nights', 2), 2),
            'max_months': self._to_int(get('max_months', 3), 3),
            'weekly_discount': self._to_float(get('weekly_discount', 10.0), 10.0),
            'weekly_nights': self._to_int(get('weekly_nights', 7), 7),
            'monthly_discount': self._to_float(get('monthly_discount', 20.0), 20.0),
            'monthly_nights': self._to_int(get('monthly_nights', 30), 30),
        }

    def get_api_credentials(self):
        """
        Reproduit la logique : si la clé contient 'user:key', on splitte.
        Sinon on utilise user_id + api_key depuis ir.config_parameter.
        """
        s = self._get_settings()
        api_key = s['billetweb_api_key'] or ''
        user_id = s['billetweb_user_id'] or ''
        if ':' in api_key:
            user, key = api_key.split(':', 1)
            return user, key
        return (user_id or None), api_key

    # ---------------------------
    # Workflow
    # ---------------------------
    def action_confirm(self):
        """Confirme la réservation et crée la commande Billetweb (synchrone ou via queue_job si dispo)."""
        self.ensure_one()
        self.state = 'confirmed'

        # Si queue_job est installé et que with_delay est disponible, exécuter en asynchrone
        if hasattr(self, 'with_delay'):
            self.with_delay()._create_billetweb_order()
        else:
            self._create_billetweb_order()
        return True

    def _create_billetweb_order(self):
        """Crée une commande sur Billetweb via l'API"""
        self.ensure_one()
        settings = self._get_settings()

        # Vérification basique de la clé API
        if not settings['billetweb_api_key'] or settings['billetweb_api_key'] == 'VOTRE_CLE_API':
            msg = _("Clé API Billetweb non configurée. Veuillez configurer la clé API dans "
                    "Paramètres > Réservations / Billetweb.")
            _logger.warning(msg)
            self.message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
            return

        # Logo (optionnel) - Non utilisé dans le payload actuel, conservé à titre d'exemple
        company = self.env.company
        logo_url = False
        if company.partner_id.image_1920:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            logo_url = f'{base_url}/web/image/res.partner/{company.partner_id.id}/image_1920'

        # Identifiants
        user, key = self.get_api_credentials()
        if not key or key == 'VOTRE_CLE_API':
            msg = _("Clé API Billetweb non configurée. Veuillez configurer la clé API dans "
                    "Paramètres > Réservations / Billetweb.")
            _logger.warning(msg)
            self.message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
            return

        # Construction de l'URL (Billetweb: user facultatif si clé au format 'user:key' déjà split)
        if user:
            api_url = f'https://www.billetweb.fr/api/attendees?user={user}&key={key}&version=1'
        else:
            api_url = f'https://www.billetweb.fr/api/attendees?key={key}&version=1'

        # Payload (à ajuster selon la doc Billetweb si besoin)
        lastname = ' '.join(self.partner_id.name.split()[1:]) if len(self.partner_id.name.split()) > 1 else self.partner_id.name
        firstname = self.partner_id.name.split()[0] if self.partner_id.name else ''
        payload = {
            'data': [
                {
                    'name': lastname,
                    'firstname': firstname,
                    'email': self.partner_id.email,
                    'session': settings['billetweb_event_id'],
                    'payment_type': 'other',  # ou 'card', 'cash', 'check'
                    'request_id': self.name,
                    'products': [
                        {
                            'ticket': settings['billetweb_ticket_id'],
                            'name': lastname,
                            'firstname': firstname,
                            'email': self.partner_id.email,
                            'price': str(self.total_amount*8.38/1000),
                            'reference': self.name,
                            'custom': {
                                'logement': self.product_id.name,
                                'date_debut': str(self.start_date),
                                'date_fin': str(self.end_date),
                                'nuits': str(self.nights),
                            },
                            'request_id': f'{self.name}-1',
                        }
                    ]
                }
            ]
        }

        try:
            _logger.info('Envoi de la commande Billetweb pour %s', self.name)
            _logger.debug('URL: %s', api_url)
            _logger.debug('Payload: %s', json.dumps(payload, indent=2))

            response = requests.post(api_url, json=payload, timeout=30)
            _logger.info('Réponse Billetweb - Status: %s', response.status_code)
            _logger.debug('Réponse brute: %s', response.text[:500])

            response.raise_for_status()

            # La réponse doit être du JSON
            try:
                result = response.json()
            except ValueError:
                error_msg = _("La réponse de Billetweb n'est pas du JSON valide. Réponse: %s") % response.text[:200]
                _logger.error(error_msg)
                self.message_post(body=f"Erreur Billetweb: {error_msg}",
                                  message_type='comment', subtype_xmlid='mail.mt_note')
                return

            # Cas succès (liste d'objets)
            if isinstance(result, list) and len(result) > 0:
                order_data = result[0]
                self.billetweb_order_id = order_data.get('id', '')
                if self.billetweb_order_id:
                    # URL de gestion de commande (à confirmer selon la doc Billetweb)
                    self.billetweb_payment_url = f'https://www.billetweb.fr/my_order.php?order_id={self.billetweb_order_id}'
                    self._send_payment_email()
                    self.state = 'payment_sent'
                    _logger.info('Commande Billetweb créée avec succès: %s', self.billetweb_order_id)
                else:
                    error_msg = result[0].get('error', 'Format de réponse inattendu')
                    _logger.error('Erreur Billetweb: %s', error_msg)
                    _logger.debug('Réponse complète: %s', json.dumps(result, indent=2))
                    self.message_post(body=f"Erreur lors de la création de la commande Billetweb: {error_msg}",
                                      message_type='comment', subtype_xmlid='mail.mt_note')
            else:
                # Format inattendu
                _logger.error('Réponse Billetweb inattendue: %s', json.dumps(result, indent=2))
                self.message_post(body="Réponse Billetweb inattendue.",
                                  message_type='comment', subtype_xmlid='mail.mt_note')

        except requests.exceptions.HTTPError as e:
            error_msg = f"Erreur HTTP {e.response.status_code}: {e.response.text[:200]}"
            _logger.error('Erreur HTTP Billetweb: %s', error_msg)
            self.message_post(body=f"Erreur de connexion à Billetweb: {error_msg}",
                              message_type='comment', subtype_xmlid='mail.mt_note')

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error('Erreur API Billetweb: %s', error_msg)
            self.message_post(body=f"Erreur de connexion à Billetweb: {error_msg}",
                              message_type='comment', subtype_xmlid='mail.mt_note')

    def _send_payment_email(self):
        """Envoie l'email avec le lien de paiement (template optionnel)"""
        self.ensure_one()
        template = self.env.ref('os_rental.email_template_payment_link', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    def action_cancel(self):
        self.state = 'cancelled'

    def action_mark_paid(self):
        """Marque la réservation comme payée (ex.: webhook Billetweb)"""
        self.state = 'paid'

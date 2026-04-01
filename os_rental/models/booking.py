# -*- coding: utf-8 -*-
# os_rental/models/booking.py  — version complète avec :
#   - action_mark_paid()  : passage en "payé" + email de confirmation
#   - _send_paid_email()  : envoi du template email_template_booking_paid
#   - _cron_sync_billetweb_payments() : cron horaire de rattrapage
#   - webhook /booking/webhook/billetweb : utilise order_paid de l'API attendees

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import logging
import math

_logger = logging.getLogger(__name__)


class BookingReservation(models.Model):
    _name = 'booking.reservation'
    _description = 'Réservation de Logement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ── Identification ────────────────────────────────────────────────────────
    name = fields.Char(
        string='Référence', required=True, copy=False,
        readonly=True, default='New', tracking=True,
    )
    partner_id  = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    product_id  = fields.Many2one(
        'product.template', string='Logement', required=True,
        domain=[('is_accommodation', '=', True)], tracking=True,
    )
    company_id  = fields.Many2one(
        'res.company', string='Société',
        default=lambda self: self.env.company, required=True,
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    start_date = fields.Date(string="Date d'arrivée", required=True, tracking=True)
    end_date   = fields.Date(string='Date de départ',  required=True, tracking=True)
    nights     = fields.Integer(string='Nuits', compute='_compute_nights', store=True)

    # ── Voyageurs ─────────────────────────────────────────────────────────────
    guests_requested = fields.Integer(string='Voyageurs demandés', default=1)
    guests_billed    = fields.Integer(
        string='Voyageurs facturés', compute='_compute_amounts', store=True)
    floor_applied    = fields.Boolean(
        string='Plancher appliqué', compute='_compute_amounts', store=True)

    # ── Tarification ──────────────────────────────────────────────────────────
    rate_per_person  = fields.Float(string='Tarif / pers / nuit (XPF)', required=True)
    nightly_rate     = fields.Float(string='Tarif / nuit (calculé)',
                                    compute='_compute_nightly_rate', store=True)
    subtotal         = fields.Float(compute='_compute_amounts', store=True)
    discount_percent = fields.Float(compute='_compute_amounts', store=True)
    discount_amount  = fields.Float(compute='_compute_amounts', store=True)
    total_amount     = fields.Float(compute='_compute_amounts', store=True)

    # ── Workflow ──────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',        'Brouillon'),
        ('confirmed',    'Confirmé'),
        ('payment_sent', 'Lien de paiement envoyé'),
        ('paid',         'Payé'),
        ('cancelled',    'Annulé'),
    ], string='État', default='draft', required=True, tracking=True)

    # ── Billetweb ─────────────────────────────────────────────────────────────
    billetweb_order_id    = fields.Char(string='ID Commande Billetweb')
    billetweb_payment_url = fields.Char(string='URL Paiement Billetweb')

    notes = fields.Text(string='Notes')

    # ── Réservations externes (Airbnb, Booking.com…) ──────────────────────────
    is_external = fields.Boolean(
        string='Réservation externe', default=False,
        help="Importée depuis un calendrier iCal externe (Airbnb, Booking.com…).",
    )
    external_uid = fields.Char(
        string='UID iCal',
        help="Identifiant unique de l'événement dans le calendrier source.",
        index=True,
    )
    external_source_id = fields.Many2one(
        'booking.ical.source', string='Source',
        ondelete='set null',
    )

    # ── Méthode à ajouter dans la classe BookingReservation ──────────────────────

    @api.model
    def _generate_ical_for_product(self, product_id):
        """
        Génère un flux iCal pour un logement donné.
        Inclut toutes les réservations confirmées / en attente / payées.
        Utilisé par le contrôleur /booking/ical/<product_id>.ics
        """
        bookings = self.search([
            ('product_id', '=', product_id),
            ('state', 'in', ['confirmed', 'payment_sent', 'paid']),
            ('end_date', '>=', fields.Date.today()),
        ])

        lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Belrose Place//Odoo Booking//FR',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'X-WR-CALNAME:Belrose Place — Réservations',
            'X-WR-TIMEZONE:Pacific/Tahiti',
        ]

        for b in bookings:
            # Formatage dates sans heure (format DATE) — compatible Airbnb/Booking
            dtstart = b.start_date.strftime('%Y%m%d')
            dtend = b.end_date.strftime('%Y%m%d')
            # Timestamp de création pour DTSTAMP
            dtstamp = (b.create_date or fields.Datetime.now()).strftime('%Y%m%dT%H%M%SZ')
            uid = f'{b.name}@belroseplace.site'

            if b.is_external:
                summary = f'Réservé ({b.external_source_id.name if b.external_source_id else "Externe"})'
            else:
                summary = f'Réservé — {b.product_id.name}'

            lines += [
                'BEGIN:VEVENT',
                f'UID:{uid}',
                f'DTSTAMP:{dtstamp}',
                f'DTSTART;VALUE=DATE:{dtstart}',
                f'DTEND;VALUE=DATE:{dtend}',
                f'SUMMARY:{summary}',
                f'STATUS:CONFIRMED',
                'TRANSP:OPAQUE',
                'END:VEVENT',
            ]

        lines.append('END:VCALENDAR')
        return '\r\n'.join(lines)

    # ════════════════════════════════════════════════════════════════════════
    # CRUD
    # ════════════════════════════════════════════════════════════════════════

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = (
                self.env['ir.sequence'].next_by_code('booking.reservation') or 'New'
            )
        return super().create(vals)

    # ════════════════════════════════════════════════════════════════════════
    # COMPUTES
    # ════════════════════════════════════════════════════════════════════════

    @api.depends('start_date', 'end_date')
    def _compute_nights(self):
        for b in self:
            if b.start_date and b.end_date and b.end_date > b.start_date:
                b.nights = (b.end_date - b.start_date).days
            else:
                b.nights = 0

    @api.depends('nights', 'rate_per_person', 'guests_requested', 'product_id')
    def _compute_amounts(self):
        s = self._get_settings()
        for b in self:
            if not b.nights or not b.rate_per_person:
                b.guests_billed = b.guests_requested or 1
                b.floor_applied = False
                b.subtotal = b.discount_percent = b.discount_amount = b.total_amount = 0.0
                continue
            cap   = b.product_id.max_occupancy or 1
            floor = math.ceil(cap / 2)
            billed = max(b.guests_requested or 1, floor)
            b.guests_billed = billed
            b.floor_applied = billed > (b.guests_requested or 1)
            sub = billed * b.rate_per_person * b.nights
            if b.nights >= s['monthly_nights']:
                pct = s['monthly_discount']
            elif b.nights >= s['weekly_nights']:
                pct = s['weekly_discount']
            else:
                pct = 0.0
            disc = sub * pct / 100
            b.subtotal         = round(sub)
            b.discount_percent = pct
            b.discount_amount  = round(disc)
            b.total_amount     = round(sub - disc)

    @api.depends('guests_billed', 'rate_per_person')
    def _compute_nightly_rate(self):
        for b in self:
            b.nightly_rate = (b.guests_billed or 1) * b.rate_per_person

    # ════════════════════════════════════════════════════════════════════════
    # CONTRAINTES
    # ════════════════════════════════════════════════════════════════════════

    @api.constrains('start_date', 'end_date', 'product_id', 'state')
    def _check_dates_and_availability(self):
        s = self._get_settings()
        for b in self:
            if not b.start_date or not b.end_date:
                continue
            if b.start_date >= b.end_date:
                raise ValidationError(_("La date de départ doit être après la date d'arrivée."))
            if b.nights < s['min_nights']:
                raise ValidationError(_("Le minimum est de %d nuits.") % s['min_nights'])
            if b.nights > s['max_months'] * 30:
                raise ValidationError(_("La durée maximum est de %d mois.") % s['max_months'])
            if b.state == 'cancelled':
                continue
            overlap = self.env['booking.reservation'].search([
                ('product_id', '=', b.product_id.id),
                ('state', 'in', ['confirmed', 'payment_sent', 'paid']),
                ('id', '!=', b.id),
                ('start_date', '<', b.end_date),
                ('end_date',   '>', b.start_date),
            ], limit=1)
            if overlap:
                raise ValidationError(
                    _("Ce logement n'est pas disponible pour ces dates.\n"
                      "Réservation en conflit : %s") % overlap.name
                )

    # ════════════════════════════════════════════════════════════════════════
    # ONCHANGE
    # ════════════════════════════════════════════════════════════════════════

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.rate_per_person = self.product_id.rate_per_person

    # ════════════════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════════════════

    def _get_param(self, key, default=None):
        return self.env['ir.config_parameter'].sudo().get_param(f'booking.{key}', default)

    @staticmethod
    def _to_int(v, d=0):
        try: return int(v)
        except (TypeError, ValueError): return d

    @staticmethod
    def _to_float(v, d=0.0):
        try: return float(v)
        except (TypeError, ValueError): return d

    def _get_settings(self):
        g = self._get_param
        return {
            'billetweb_user_id':   g('billetweb_user_id') or None,
            'billetweb_api_key':   g('billetweb_api_key') or '',
            'billetweb_event_id':  g('billetweb_event_id') or '',
            'billetweb_ticket_id': g('billetweb_ticket_id') or '',
            'cgv_url':             g('cgv_url') or '',
            'min_nights':          self._to_int(g('min_nights', 2), 2),
            'max_months':          self._to_int(g('max_months', 3), 3),
            'weekly_discount':     self._to_float(g('weekly_discount', 10.0), 10.0),
            'weekly_nights':       self._to_int(g('weekly_nights', 7), 7),
            'monthly_discount':    self._to_float(g('monthly_discount', 20.0), 20.0),
            'monthly_nights':      self._to_int(g('monthly_nights', 30), 30),
        }

    def get_api_credentials(self):
        s = self._get_settings()
        key  = s['billetweb_api_key']
        user = s['billetweb_user_id']
        if ':' in (key or ''):
            user, key = key.split(':', 1)
        return (user or None), key

    # ════════════════════════════════════════════════════════════════════════
    # WORKFLOW
    # ════════════════════════════════════════════════════════════════════════

    def action_confirm(self):
        self.ensure_one()
        self.state = 'confirmed'
        if hasattr(self, 'with_delay'):
            self.with_delay()._create_billetweb_order()
        else:
            self._create_billetweb_order()
        return True

    def action_cancel(self):
        self.state = 'cancelled'

    def action_mark_paid(self):
        """
        Passe la réservation en état 'paid' et envoie l'email de confirmation
        au client. Idempotent : ne fait rien si déjà payé.
        """
        for booking in self:
            if booking.state == 'paid':
                continue
            booking.state = 'paid'
            booking.message_post(
                body=_("✅ Paiement confirmé — statut mis à jour."),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            booking._send_paid_email()

    # ════════════════════════════════════════════════════════════════════════
    # EMAILS
    # ════════════════════════════════════════════════════════════════════════

    def _send_payment_email(self):
        """Email avec lien de paiement (appelé après création commande Billetweb)."""
        self.ensure_one()
        template = self.env.ref(
            'os_rental.email_template_payment_link', raise_if_not_found=False)
        if not template or not self.partner_id.email:
            return
        email_values = {
            'email_to':   self.partner_id.email,
            'email_from': (
                self.company_id.email
                or self.env.user.email
                or self.env['ir.config_parameter'].sudo().get_param('mail.catchall.email')
                or ''
            ),
        }
        try:
            template.send_mail(self.id, force_send=True, email_values=email_values)
        except Exception as e:
            _logger.error('Erreur envoi email lien paiement %s : %s', self.name, e)

    def _send_paid_email(self):
        """Email de confirmation de paiement (appelé par action_mark_paid)."""
        self.ensure_one()
        template = self.env.ref(
            'os_rental.email_template_booking_paid', raise_if_not_found=False)
        if not template:
            _logger.warning('Template email_template_booking_paid introuvable pour %s', self.name)
            return
        if not self.partner_id.email:
            _logger.warning('Pas d\'email pour le client de %s', self.name)
            return
        email_values = {
            'email_to':   self.partner_id.email,
            'email_from': (
                self.company_id.email
                or self.env.user.email
                or self.env['ir.config_parameter'].sudo().get_param('mail.catchall.email')
                or ''
            ),
            'subject': f'✅ Paiement confirmé — Réservation {self.name}',
        }
        try:
            template.send_mail(self.id, force_send=True, email_values=email_values)
            _logger.info('Email confirmation paiement envoyé à %s pour %s',
                         self.partner_id.email, self.name)
        except Exception as e:
            _logger.error('Erreur envoi email confirmation paiement %s : %s', self.name, e)
            self.message_post(
                body=f"⚠️ Erreur envoi email confirmation : {e}",
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

    # ════════════════════════════════════════════════════════════════════════
    # BILLETWEB — CRÉATION COMMANDE
    # ════════════════════════════════════════════════════════════════════════

    def _create_billetweb_order(self):
        self.ensure_one()
        settings = self._get_settings()

        if not settings['billetweb_api_key'] or settings['billetweb_api_key'] == 'VOTRE_CLE_API':
            msg = _("Clé API Billetweb non configurée.")
            _logger.warning(msg)
            self.message_post(body=msg, message_type='comment', subtype_xmlid='mail.mt_note')
            return

        user, key = self.get_api_credentials()
        if not key or key == 'VOTRE_CLE_API':
            return

        event_id = settings['billetweb_event_id']
        base     = 'https://www.billetweb.fr/api'
        qs       = f"user={user}&key={key}&version=1" if user else f"key={key}&version=1"
        api_url  = f'{base}/event/{event_id}/add_order?{qs}'

        parts     = self.partner_id.name.split()
        firstname = parts[0] if parts else ''
        lastname  = ' '.join(parts[1:]) if len(parts) > 1 else self.partner_id.name

        payload = {'data': [{
            'name':         lastname,
            'firstname':    firstname,
            'email':        self.partner_id.email or 'noreply@example.com',
            'session':      event_id,
            'payment_type': 'reservation',
            'request_id':   self.name,
            'products': [{
                'ticket':     settings['billetweb_ticket_id'],
                'name':       lastname,
                'firstname':  firstname,
                'email':      self.partner_id.email or 'noreply@example.com',
                'price':      str(self.total_amount * 8.38 / 1000),
                'reference':  self.name,
                'custom': {
                    'Logement':        self.product_id.name,
                    'Date début':      str(self.start_date),
                    'Date fin':        str(self.end_date),
                    'Nuits':           str(self.nights),
                    'Voyageurs':       str(self.guests_billed),
                    'Tarif/pers/nuit': str(self.rate_per_person),
                },
                'request_id': f'{self.name}-1',
            }],
        }]}

        try:
            _logger.info('Envoi commande Billetweb pour %s', self.name)
            resp = requests.post(api_url, json=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()

            if isinstance(result, list) and result:
                order_data = result[0]
                order_id   = str(order_data.get('id', ''))

                if order_id:
                    self.billetweb_order_id = order_id

                    # Récupérer l'URL de paiement via /attendees
                    att_qs  = f"user={user}&key={key}&version=1&order_id={order_id}" if user \
                              else f"key={key}&version=1&order_id={order_id}"
                    att_url = f'{base}/attendees?{att_qs}'
                    att_r   = requests.get(att_url, timeout=30)
                    att_r.raise_for_status()
                    att_data = att_r.json()
                    if isinstance(att_data, list) and att_data:
                        payment_url = att_data[0].get('order_management', '')
                        if payment_url:
                            self.billetweb_payment_url = payment_url

                    msg = f"✅ Commande Billetweb créée : {order_id}"
                    if self.billetweb_payment_url:
                        msg += (f"<br/>URL : <a href='{self.billetweb_payment_url}'"
                                f" target='_blank'>{self.billetweb_payment_url}</a>")
                    self.message_post(body=msg, message_type='comment',
                                      subtype_xmlid='mail.mt_note')

                    self.state = 'payment_sent' if self.billetweb_payment_url else 'confirmed'

        except requests.exceptions.RequestException as e:
            _logger.error('Erreur API Billetweb : %s', e)
            self.message_post(
                body=f"❌ Erreur Billetweb : {e}",
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

    # ════════════════════════════════════════════════════════════════════════
    # BILLETWEB — INTERROGATION ATTENDEES (webhook + cron)
    # ════════════════════════════════════════════════════════════════════════

    def _fetch_billetweb_attendees(self, order_id=None):
        """
        Appelle GET /api/attendees et retourne la liste brute.
        Si order_id est fourni, filtre sur cette commande.
        Retourne [] en cas d'erreur.
        """
        user, key = self.get_api_credentials()
        if not key:
            return []

        qs = f"user={user}&key={key}&version=1" if user else f"key={key}&version=1"
        if order_id:
            qs += f"&order_id={order_id}"

        settings  = self._get_settings()
        event_id  = settings['billetweb_event_id']
        url = f"https://www.billetweb.fr/api/event/{event_id}/attendees?{qs}"

        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
        except Exception as e:
            _logger.error('Erreur récupération attendees Billetweb : %s', e)
            return []

    @api.model
    def _cron_sync_billetweb_payments(self):
        """
        Tâche planifiée (toutes les heures).
        Interroge l'API Billetweb pour chaque réservation en état
        'confirmed' ou 'payment_sent' ayant un billetweb_order_id,
        et passe en 'paid' celles dont order_paid == '1'.

        Sécurité : on ne traite que les réservations actives (non annulées,
        non déjà payées) pour limiter les appels API.
        """
        pending = self.search([
            ('state', 'in', ['confirmed', 'payment_sent']),
            ('billetweb_order_id', '!=', False),
            ('billetweb_order_id', '!=', ''),
        ])

        if not pending:
            return

        _logger.info('Cron Billetweb : %d réservation(s) à vérifier', len(pending))

        for booking in pending:
            try:
                attendees = booking._fetch_billetweb_attendees(
                    order_id=booking.billetweb_order_id)

                # order_paid = "1" signifie paiement encaissé
                paid = any(
                    str(a.get('order_paid', '0')) == '1'
                    for a in attendees
                )

                if paid:
                    _logger.info('Cron : paiement détecté pour %s', booking.name)
                    booking.action_mark_paid()

            except Exception as e:
                # On logue mais on ne bloque pas le cron pour les autres
                _logger.error('Cron Billetweb — erreur sur %s : %s', booking.name, e)

        _logger.info('Cron Billetweb terminé.')

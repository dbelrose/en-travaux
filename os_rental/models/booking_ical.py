# -*- coding: utf-8 -*-
# os_rental/models/booking_ical.py

from odoo import models, fields, api, _
import requests
import logging
import re
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class BookingIcalSource(models.Model):
    _name = 'booking.ical.source'
    _description = 'Source iCal externe (Airbnb, Booking.com…)'
    _order = 'product_id, name'

    name = fields.Char(string='Plateforme', required=True,
                       help="Ex. : Airbnb, Booking.com, VRBO…")
    product_id = fields.Many2one(
        'product.template', string='Logement', required=True,
        domain=[('is_accommodation', '=', True)], ondelete='cascade',
    )
    ical_url = fields.Char(
        string='URL iCal (import)',
        help="URL publique fournie par la plateforme externe.",
    )
    # URL calculée pour l'export Odoo → plateforme
    ical_export_url = fields.Char(
        string="URL iCal Odoo (à copier dans Airbnb / Booking.com)",
        compute='_compute_ical_export_url',
    )
    active       = fields.Boolean(default=True)
    last_sync    = fields.Datetime(string='Dernière synchro', readonly=True)
    last_error   = fields.Char(string='Dernière erreur', readonly=True)
    booking_count = fields.Integer(
        string='Réservations importées',
        compute='_compute_booking_count',
    )

    @api.depends('product_id')
    def _compute_booking_count(self):
        for src in self:
            src.booking_count = self.env['booking.reservation'].search_count([
                ('external_source_id', '=', src.id),
            ])

    @api.depends('product_id')
    def _compute_ical_export_url(self):
        """
        Construit l'URL publique du flux iCal Odoo pour ce logement.
        Utilise le base_url du site web configuré dans Odoo.
        """
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', 'https://votre-domaine.com')
        for src in self:
            if src.product_id:
                src.ical_export_url = f"{base}/booking/ical/{src.product_id.id}.ics"
            else:
                src.ical_export_url = False

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_sync_now(self):
        self.ensure_one()
        self._sync()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title':   _('Synchronisation terminée'),
                'message': self.last_error or _('Import réussi.'),
                'type':    'warning' if self.last_error else 'success',
                'sticky':  False,
            },
        }

    # ── Synchronisation ───────────────────────────────────────────────────────

    def _sync(self):
        self.ensure_one()
        if not self.ical_url:
            return

        try:
            resp = requests.get(self.ical_url, timeout=20)
            resp.raise_for_status()
            events = _parse_ical(resp.text)
        except Exception as e:
            self.last_error = str(e)[:200]
            _logger.error('iCal import [%s / %s] : %s',
                          self.name, self.product_id.name, e)
            return

        Reservation = self.env['booking.reservation']
        imported = cancelled = 0

        for ev in events:
            uid       = ev.get('uid', '')
            dtstart   = ev.get('dtstart')
            dtend     = ev.get('dtend')
            summary   = ev.get('summary', self.name)
            ev_status = ev.get('status', 'CONFIRMED').upper()

            if not uid or not dtstart or not dtend:
                continue

            existing = Reservation.search([
                ('external_uid', '=', uid),
                ('external_source_id', '=', self.id),
            ], limit=1)

            # Événements passés ou annulés
            if dtend <= date.today() or ev_status == 'CANCELLED':
                if existing and existing.state not in ('cancelled', 'paid'):
                    existing.sudo().write({'state': 'cancelled'})
                    cancelled += 1
                continue

            vals = {'start_date': dtstart, 'end_date': dtend}

            if existing:
                if existing.start_date != dtstart or existing.end_date != dtend:
                    existing.sudo().write(vals)
            else:
                partner = self._get_platform_partner()
                try:
                    Reservation.sudo().create({
                        'partner_id':         partner.id,
                        'product_id':         self.product_id.id,
                        'start_date':         dtstart,
                        'end_date':           dtend,
                        'rate_per_person':    0.0,
                        'guests_requested':   1,
                        'state':              'confirmed',
                        'is_external':        True,
                        'external_uid':       uid,
                        'external_source_id': self.id,
                        'notes':              f'[{self.name}] {summary}',
                    })
                    imported += 1
                except Exception as e:
                    _logger.warning('iCal : impossible de créer %s : %s', uid, e)

        self.last_sync  = fields.Datetime.now()
        self.last_error = None
        _logger.info('iCal [%s / %s] : %d importée(s), %d annulée(s)',
                     self.name, self.product_id.name, imported, cancelled)

    def _get_platform_partner(self):
        name = f'{self.name} (externe)'
        partner = self.env['res.partner'].sudo().search(
            [('name', '=', name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].sudo().create({'name': name})
        return partner

    @api.model
    def _cron_sync_all(self):
        sources = self.search([('active', '=', True), ('ical_url', '!=', False)])
        _logger.info('Cron iCal : %d source(s) à synchroniser', len(sources))
        for src in sources:
            try:
                src._sync()
            except Exception as e:
                _logger.error('Cron iCal — %s / %s : %s',
                              src.name, src.product_id.name, e)
        _logger.info('Cron iCal terminé.')


# ════════════════════════════════════════════════════════════════════════════
# PARSEUR iCal MINIMAL (sans dépendance externe)
# ════════════════════════════════════════════════════════════════════════════

def _parse_ical(text):
    # Dépliage des lignes (line-folding RFC 5545)
    text = re.sub(r'\r?\n[ \t]', '', text)
    events = []
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == 'BEGIN:VEVENT':
            current = {}
            continue
        if line == 'END:VEVENT':
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ':' not in line:
            continue
        key_part, _, value = line.partition(':')
        key = key_part.split(';')[0].upper()
        if key == 'UID':
            current['uid'] = value.strip()
        elif key == 'SUMMARY':
            current['summary'] = value.strip()
        elif key == 'STATUS':
            current['status'] = value.strip().upper()
        elif key == 'DTSTART':
            current['dtstart'] = _parse_ical_date(value.strip())
        elif key == 'DTEND':
            current['dtend'] = _parse_ical_date(value.strip())
    return [e for e in events if e.get('dtstart') and e.get('dtend')]


def _parse_ical_date(value):
    value = value.strip().rstrip('Z')
    try:
        if 'T' in value:
            return datetime.strptime(value[:15], '%Y%m%dT%H%M%S').date()
        return datetime.strptime(value[:8], '%Y%m%d').date()
    except ValueError:
        _logger.warning('iCal : date non parseable : %s', value)
        return None

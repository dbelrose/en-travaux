# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_accommodation = fields.Boolean(
        string='Est un logement',
        compute='_compute_is_accommodation', store=True,
    )
    # Ancien champ conservé pour compatibilité (tarif global/nuit)
    nightly_rate = fields.Float(string='Tarif par nuit (logement entier)')

    # Nouveau : tarif par personne / par nuit
    rate_per_person = fields.Float(
        string='Tarif par personne / nuit (XPF)',
        help="Tarif unitaire par personne et par nuit. "
             "Le plancher est calculé sur 50% de la capacité maximale.",
    )
    max_occupancy = fields.Integer(string='Capacité maximum (personnes)')
    booking_ids = fields.One2many('booking.reservation', 'product_id', string='Réservations')

    @api.depends('categ_id')
    def _compute_is_accommodation(self):
        categ = self.env.ref(
            'os_hospitality_managment.product_category_tdsmdt',
            raise_if_not_found=False,
        )
        for product in self:
            product.is_accommodation = bool(categ and product.categ_id == categ)

    # ── Calcul du prix pour un nombre de voyageurs donné ──────────────────────

    def compute_price(self, guests, nights, weekly_discount=0.0, monthly_discount=0.0,
                      weekly_nights=7, monthly_nights=30):
        """
        Retourne un dict de tarification pour (guests, nights).

        Règle plancher : le nombre de personnes facturé est
            max(guests, ceil(max_occupancy / 2))
        soit au minimum la moitié de la capacité.

        Retourne :
            guests_requested  : voyageurs demandés
            guests_billed     : voyageurs facturés (après plancher)
            floor_applied     : True si le plancher a été déclenché
            rate_per_person   : tarif unitaire /pers /nuit
            subtotal          : guests_billed × rate × nights (avant remise)
            discount_percent  : % de remise durée
            discount_amount   : montant de la remise
            total             : montant final
        """
        self.ensure_one()
        import math
        floor = math.ceil(self.max_occupancy / 2) if self.max_occupancy else 1
        guests_billed = max(int(guests), floor)
        floor_applied = guests_billed > int(guests)

        rate = self.rate_per_person or (self.nightly_rate / max(self.max_occupancy, 1))
        subtotal = guests_billed * rate * nights

        if nights >= monthly_nights:
            discount = monthly_discount
        elif nights >= weekly_nights:
            discount = weekly_discount
        else:
            discount = 0.0

        discount_amount = subtotal * discount / 100
        total = subtotal - discount_amount

        return {
            'guests_requested': int(guests),
            'guests_billed':    guests_billed,
            'floor_applied':    floor_applied,
            'floor':            floor,
            'rate_per_person':  rate,
            'subtotal':         round(subtotal),
            'discount_percent': discount,
            'discount_amount':  round(discount_amount),
            'total':            round(total),
        }

    def get_availability(self, start_date, end_date, exclude_booking_id=None):
        self.ensure_one()
        domain = [
            ('product_id', '=', self.id),
            ('state', 'in', ['confirmed', 'payment_sent', 'paid']),
            ('start_date', '<', end_date),
            ('end_date',   '>', start_date),
        ]
        if exclude_booking_id:
            domain.append(('id', '!=', exclude_booking_id))
        return not self.env['booking.reservation'].search(domain, limit=1)

    def get_booking_calendar_data(self, start_date, end_date):
        self.ensure_one()
        bookings = self.env['booking.reservation'].search([
            ('product_id', '=', self.id),
            ('state', 'in', ['confirmed', 'payment_sent', 'paid']),
            ('start_date', '<=', end_date),
            ('end_date',   '>=', start_date),
        ])
        colors = {
            'draft': '#6c757d', 'confirmed': '#17a2b8',
            'payment_sent': '#ffc107', 'paid': '#28a745', 'cancelled': '#dc3545',
        }
        return [{
            'id':      b.id,
            'name':    b.name,
            'start':   b.start_date.isoformat(),
            'end':     b.end_date.isoformat(),
            'partner': b.partner_id.name,
            'state':   b.state,
            'color':   colors.get(b.state, '#6c757d'),
        } for b in bookings]

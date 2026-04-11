# -*- coding: utf-8 -*-
# os_website_belrose_place/controllers/main.py
#
# Correctif POST-Redirect-GET :
#   reservation_submit  → crée la réservation puis REDIRIGE vers /reservation/confirmation/<id>
#   reservation_confirm → nouvelle route GET, sûre au rechargement (F5 / auto-refresh)

from odoo import http
from odoo.http import request
from datetime import datetime, date, timedelta
import json
import math


class BelrosePlaceWebsite(http.Controller):

    # ── Pages statiques ───────────────────────────────────────────────────────

    @http.route('/', type='http', auth='public', website=True)
    def homepage(self, **kwargs):
        return request.render('os_website_belrose_place.homepage')

    @http.route('/cheque-cadeau-vacances', type='http', auth='public', website=True)
    def cheque_cadeau(self, **kwargs):
        return request.render('os_website_belrose_place.cheque_cadeau_vacances')

    @http.route('/mentions-legales', type='http', auth='public', website=True)
    def mentions_legales(self, **kwargs):
        return request.render('os_website_belrose_place.mentions_legales')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_config(self):
        ICP = request.env['ir.config_parameter'].sudo()
        return {
            'min_nights':       int(ICP.get_param('booking.min_nights', 2)),
            'max_months':       int(ICP.get_param('booking.max_months', 3)),
            'weekly_nights':    int(ICP.get_param('booking.weekly_nights', 7)),
            'weekly_discount':  float(ICP.get_param('booking.weekly_discount', 10.0)),
            'monthly_nights':   int(ICP.get_param('booking.monthly_nights', 30)),
            'monthly_discount': float(ICP.get_param('booking.monthly_discount', 20.0)),
        }

    def _price_breakdown(self, product, guests, nights, config):
        if hasattr(product, 'compute_price'):
            result = product.compute_price(
                guests=guests, nights=nights,
                weekly_discount=config['weekly_discount'],
                monthly_discount=config['monthly_discount'],
                weekly_nights=config['weekly_nights'],
                monthly_nights=config['monthly_nights'],
            )
            result.setdefault('nights', nights)
            return result
        floor = math.ceil(product.max_occupancy / 2) if product.max_occupancy else 1
        billed = max(int(guests), floor)
        rate = getattr(product, 'rate_per_person', None) or (
            product.nightly_rate / max(product.max_occupancy, 1)
        )
        sub = billed * rate * nights
        pct = 0.0
        if nights >= config['monthly_nights']:
            pct = config['monthly_discount']
        elif nights >= config['weekly_nights']:
            pct = config['weekly_discount']
        disc = sub * pct / 100
        return {
            'guests_requested': int(guests),
            'guests_billed':    billed,
            'floor_applied':    billed > int(guests),
            'floor':            floor,
            'rate_per_person':  rate,
            'nights':           nights,
            'subtotal':         round(sub),
            'discount_percent': pct,
            'discount_amount':  round(disc),
            'total':            round(sub - disc),
        }

    # ── Étape 1 : Recherche ───────────────────────────────────────────────────

    @http.route('/reservation', type='http', auth='public', website=True)
    def reservation_search(self, start_date=None, end_date=None, guests=None, **kwargs):
        config      = self._get_config()
        results     = None
        search_done = False
        nights      = 0
        error       = None

        if start_date and end_date:
            search_done = True
            try:
                d_start  = datetime.strptime(start_date, '%Y-%m-%d').date()
                d_end    = datetime.strptime(end_date,   '%Y-%m-%d').date()
                n_guests = int(guests or 1)
                nights   = (d_end - d_start).days

                if d_start < date.today():
                    error = "La date d'arrivée ne peut pas être dans le passé."
                elif nights < config['min_nights']:
                    error = f"La durée minimale est de {config['min_nights']} nuits."
                elif nights > config['max_months'] * 30:
                    error = f"La durée maximale est de {config['max_months']} mois."
                else:
                    all_accom = request.env['product.template'].sudo().search([
                        ('is_accommodation', '=', True),
                        ('max_occupancy', '>=', n_guests),
                    ])
                    results = []
                    for p in all_accom:
                        available = p.get_availability(d_start, d_end)
                        pricing   = self._price_breakdown(p, n_guests, nights, config)
                        results.append({
                            'product':   p,
                            'available': available,
                            'nights':    nights,
                            **pricing,
                        })
                    results.sort(key=lambda r: (0 if r['available'] else 1, r['total']))
            except Exception as e:
                error = str(e)

        return request.render('os_website_belrose_place.bp_reservation_search', {
            'config':      config,
            'today':       date.today().isoformat(),
            'max_date':    (date.today() + timedelta(days=config['max_months'] * 30)).isoformat(),
            'start_date':  start_date or '',
            'end_date':    end_date or '',
            'guests':      guests or '1',
            'nights':      nights,
            'results':     results,
            'search_done': search_done,
            'error':       error,
        })

    # ── Étape 2 : Formulaire ──────────────────────────────────────────────────

    @http.route('/reservation/nouveau', type='http', auth='public', website=True)
    def reservation_form(self, product_id=None, start_date=None, end_date=None,
                         guests=None, **kwargs):
        if not product_id:
            return request.redirect('/reservation')
        product = request.env['product.template'].sudo().browse(int(product_id))
        if not product.exists() or not product.is_accommodation:
            return request.redirect('/reservation')

        config        = self._get_config()
        price_preview = None

        if start_date and end_date:
            try:
                d_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                d_end   = datetime.strptime(end_date,   '%Y-%m-%d').date()
                nights  = (d_end - d_start).days
                n_guests = int(guests or 1)
                price_preview = self._price_breakdown(product, n_guests, nights, config)
            except Exception:
                pass

        return request.render('os_website_belrose_place.bp_booking_form', {
            'product':       product,
            'config':        config,
            'today':         date.today().isoformat(),
            'max_date':      (date.today() + timedelta(days=config['max_months'] * 30)).isoformat(),
            'start_date':    start_date or '',
            'end_date':      end_date or '',
            'guests':        guests or '1',
            'price_preview': price_preview,
        })

    # ── Soumission POST → redirect GET ────────────────────────────────────────
    #
    # CORRECTIF : on ne rend plus le template ici.
    # On crée la réservation puis on redirige vers la route GET /reservation/confirmation/<id>.
    # Ainsi, F5 ou l'auto-refresh ne re-soumet JAMAIS le formulaire.

    @http.route('/reservation/soumettre', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def reservation_submit(self, **post):
        try:
            product_id = int(post.get('product_id'))
            name       = post.get('name', '').strip()
            email      = post.get('email', '').strip()
            phone      = post.get('phone', '').strip()
            start_date = datetime.strptime(post.get('start_date'), '%Y-%m-%d').date()
            end_date   = datetime.strptime(post.get('end_date'),   '%Y-%m-%d').date()
            n_guests   = int(post.get('guests', 1))
            notes      = post.get('notes', '').strip()

            if not name or not email:
                raise ValueError("Nom et email sont obligatoires.")
            if start_date >= end_date:
                raise ValueError("La date de départ doit être après la date d'arrivée.")

            partner = request.env['res.partner'].sudo().search(
                [('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': name, 'email': email, 'phone': phone,
                })

            product = request.env['product.template'].sudo().browse(product_id)
            config  = self._get_config()
            pricing = self._price_breakdown(product, n_guests,
                                            (end_date - start_date).days, config)

            booking = request.env['booking.reservation'].sudo().create({
                'partner_id':       partner.id,
                'product_id':       product.id,
                'start_date':       start_date,
                'end_date':         end_date,
                'guests_requested': n_guests,
                'rate_per_person':  pricing['rate_per_person'],
                'notes':            notes,
            })
            booking.action_confirm()

            # POST-Redirect-GET : on redirige vers la page de confirmation GET
            # pour qu'un rechargement ne re-soumette pas le formulaire.
            return request.redirect(f'/reservation/confirmation/{booking.id}')

        except Exception as e:
            return request.render('os_website_belrose_place.bp_booking_error', {
                'error_message': str(e),
                'product_id':    post.get('product_id'),
                'start_date':    post.get('start_date', ''),
                'end_date':      post.get('end_date', ''),
            })

    # ── Confirmation GET (sûre au rechargement) ───────────────────────────────

    @http.route('/reservation/confirmation/<int:booking_id>', type='http',
                auth='public', website=True)
    def reservation_confirm(self, booking_id, **kwargs):
        """
        Page de confirmation — route GET.
        Rechargeable sans risque (pas de re-soumission de formulaire).
        L'auto-refresh Javascript peut donc appeler window.location.reload()
        en toute sécurité pour attendre que billetweb_payment_url soit prêt.
        """
        booking = request.env['booking.reservation'].sudo().browse(booking_id)
        if not booking.exists():
            return request.redirect('/reservation')

        return request.render('os_website_belrose_place.bp_booking_confirmation', {
            'booking': booking,
        })

    # ── Page de paiement iframe ───────────────────────────────────────────────

    @http.route('/reservation/paiement/<int:booking_id>', type='http',
                auth='public', website=True)
    def payment_page(self, booking_id, **kwargs):
        booking = request.env['booking.reservation'].sudo().browse(booking_id)
        if not booking.exists() or not booking.billetweb_payment_url:
            return request.redirect('/reservation')

        return request.render('os_website_belrose_place.bp_payment_iframe', {
            'booking':     booking,
            'payment_url': booking.billetweb_payment_url,
        })

    # ── Mes réservations ──────────────────────────────────────────────────────

    @http.route('/reservation/mes-reservations', type='http', auth='user', website=True)
    def my_bookings(self, **kwargs):
        partner  = request.env.user.partner_id
        bookings = request.env['booking.reservation'].sudo().search(
            [('partner_id', '=', partner.id)], order='create_date desc')
        return request.render('os_website_belrose_place.bp_my_bookings', {
            'bookings': bookings,
        })

    # ── Calendrier ────────────────────────────────────────────────────────────

    @http.route('/reservation/disponibilites/<int:product_id>', type='http',
                auth='public', website=True)
    def reservation_calendar(self, product_id, **kwargs):
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists() or not product.is_accommodation:
            return request.redirect('/reservation')
        d_start = date.today()
        d_end   = d_start + timedelta(days=180)
        return request.render('os_website_belrose_place.bp_booking_calendar', {
            'product':            product,
            'calendar_data_json': json.dumps(product.get_booking_calendar_data(d_start, d_end)),
            'today':              date.today().isoformat(),
        })

    # ── AJAX disponibilité + prix ─────────────────────────────────────────────

    @http.route('/reservation/disponibilite', type='json', auth='public')
    def check_availability(self, product_id, start_date, end_date, guests=1, **kwargs):
        try:
            product  = request.env['product.template'].sudo().browse(int(product_id))
            d_start  = datetime.strptime(start_date, '%Y-%m-%d').date()
            d_end    = datetime.strptime(end_date,   '%Y-%m-%d').date()
            if d_start >= d_end:
                return {'available': False, 'error': 'Dates invalides'}
            nights   = (d_end - d_start).days
            config   = self._get_config()
            available = product.get_availability(d_start, d_end)
            pricing   = self._price_breakdown(product, int(guests), nights, config)
            return {'available': available, **pricing}
        except Exception as e:
            return {'error': str(e)}

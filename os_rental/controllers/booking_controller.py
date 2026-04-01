from odoo import http
from odoo.http import request
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class BookingController(http.Controller):

    @http.route('/booking', type='http', auth='public', website=True)
    def accommodation_list(self, **kwargs):
        accommodation_categ = request.env.ref(
            'os_hospitality_managment.product_category_tdsmdt', raise_if_not_found=False)
        if not accommodation_categ:
            accommodations = request.env['product.template'].sudo().search(
                [('is_accommodation', '=', True)])
        else:
            accommodations = request.env['product.template'].sudo().search([
                ('categ_id', '=', accommodation_categ.id),
                ('is_accommodation', '=', True),
            ])
        return request.render('os_rental.accommodation_list', {
            'accommodations': accommodations,
        })

    @http.route('/booking/new', type='http', auth='public', website=True)
    def booking_form(self, product_id=None, **kwargs):
        if not product_id:
            return request.redirect('/booking')
        product = request.env['product.template'].sudo().browse(int(product_id))
        if not product.exists() or not product.is_accommodation:
            return request.redirect('/booking')
        return request.render('os_rental.booking_form', {'product': product})

    @http.route('/booking/submit', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def booking_submit(self, **post):
        try:
            product_id = int(post.get('product_id'))
            name       = post.get('name')
            email      = post.get('email')
            phone      = post.get('phone', '')
            start_date = datetime.strptime(post.get('start_date'), '%Y-%m-%d').date()
            end_date   = datetime.strptime(post.get('end_date'),   '%Y-%m-%d').date()
            notes      = post.get('notes', '')

            partner = request.env['res.partner'].sudo().search(
                [('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create(
                    {'name': name, 'email': email, 'phone': phone})

            product = request.env['product.template'].sudo().browse(product_id)
            booking = request.env['booking.reservation'].sudo().create({
                'partner_id':  partner.id,
                'product_id':  product.id,
                'start_date':  start_date,
                'end_date':    end_date,
                'nightly_rate': product.nightly_rate,
                'notes':       notes,
            })
            booking.action_confirm()
            return request.render('os_rental.booking_confirmation', {'booking': booking})
        except Exception as e:
            return request.render('website.404', {'error_message': str(e)})

    @http.route('/booking/list', type='http', auth='user', website=True)
    def booking_list(self, **kwargs):
        partner  = request.env.user.partner_id
        bookings = request.env['booking.reservation'].sudo().search(
            [('partner_id', '=', partner.id)], order='create_date desc')
        return request.render('os_rental.booking_list_template', {'bookings': bookings})

    # ── Webhook Billetweb ─────────────────────────────────────────────────────
    #
    # Billetweb envoie un POST avec au minimum :
    #   order_id  : identifiant de la commande
    #   status    : "paid" | "cancelled" | autre
    #
    # On interroge AUSSI l'API /attendees pour lire order_paid directement,
    # ce qui est plus fiable que le champ status du webhook (qui peut varier).

    @http.route('/booking/webhook/billetweb', type='json', auth='public', csrf=False)
    def billetweb_webhook(self, **kwargs):
        try:
            order_id = kwargs.get('order_id')
            status   = kwargs.get('status', '')

            if not order_id:
                _logger.warning('Webhook Billetweb : order_id manquant')
                return {'status': 'error', 'message': 'Missing order_id'}

            booking = request.env['booking.reservation'].sudo().search(
                [('billetweb_order_id', '=', str(order_id))], limit=1)

            if not booking:
                _logger.warning('Webhook Billetweb : réservation introuvable pour order_id=%s',
                                order_id)
                return {'status': 'error', 'message': 'Booking not found'}

            # ── Stratégie double : status du webhook + vérification API ──────
            if status == 'paid':
                # Vérification API pour s'assurer que order_paid == "1"
                confirmed_paid = _verify_order_paid_via_api(booking, order_id)
                if confirmed_paid:
                    booking.action_mark_paid()
                    return {'status': 'success', 'message': 'Booking marked as paid'}
                else:
                    _logger.warning(
                        'Webhook status=paid mais order_paid != 1 pour order_id=%s', order_id)
                    return {'status': 'ignored', 'message': 'order_paid not confirmed'}

            elif status == 'cancelled':
                booking.action_cancel()
                return {'status': 'success', 'message': 'Booking cancelled'}

            # Statut inconnu : on interroge quand même l'API pour être sûr
            else:
                confirmed_paid = _verify_order_paid_via_api(booking, order_id)
                if confirmed_paid and booking.state != 'paid':
                    booking.action_mark_paid()
                    return {'status': 'success', 'message': 'Booking marked as paid via API check'}

            return {'status': 'success', 'message': 'No action needed'}

        except Exception as e:
            _logger.error('Erreur webhook Billetweb : %s', e)
            return {'status': 'error', 'message': str(e)}

    @http.route('/booking/availability', type='json', auth='public')
    def check_availability(self, product_id, start_date, end_date, **kwargs):
        try:
            product = request.env['product.template'].sudo().browse(int(product_id))
            start   = datetime.strptime(start_date, '%Y-%m-%d').date()
            end     = datetime.strptime(end_date,   '%Y-%m-%d').date()
            available = product.get_availability(start, end)
            delta  = end - start
            nights = delta.days
            config = request.env['booking.config'].sudo().get_config()
            subtotal = nights * product.nightly_rate
            discount = 0.0
            if config:
                if nights >= config.monthly_nights:
                    discount = config.monthly_discount
                elif nights >= config.weekly_nights:
                    discount = config.weekly_discount
            discount_amount = subtotal * (discount / 100)
            total = subtotal - discount_amount
            return {
                'available':       available,
                'nights':          nights,
                'subtotal':        subtotal,
                'discount_percent': discount,
                'discount_amount': discount_amount,
                'total':           total,
            }
        except Exception as e:
            return {'error': str(e)}

    @http.route('/booking/calendar/<int:product_id>', type='http', auth='public', website=True)
    def booking_calendar(self, product_id, **kwargs):
        from datetime import date, timedelta
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists() or not product.is_accommodation:
            return request.redirect('/booking')
        start_date    = date.today()
        end_date      = start_date + timedelta(days=180)
        calendar_data = product.get_booking_calendar_data(start_date, end_date)
        return request.render('os_rental.booking_calendar_view', {
            'product':       product,
            'calendar_data': calendar_data,
        })


# ── Fonction utilitaire (hors classe) ─────────────────────────────────────────

def _verify_order_paid_via_api(booking, order_id):
    """
    Appelle GET /api/event/:id/attendees?order_id=...
    et retourne True si au moins un attendee a order_paid == "1".
    """
    try:
        attendees = booking._fetch_billetweb_attendees(order_id=str(order_id))
        return any(str(a.get('order_paid', '0')) == '1' for a in attendees)
    except Exception as e:
        _logger.error('_verify_order_paid_via_api erreur : %s', e)
        return False

from odoo import http
from odoo.http import request
from datetime import datetime


class BookingController(http.Controller):

    @http.route('/booking', type='http', auth='public', website=True)
    def accommodation_list(self, **kwargs):
        """Liste des logements disponibles"""
        accommodation_categ = request.env.ref('os_hospitality_managment.product_category_tdsmdt')
        accommodations = request.env['product.template'].sudo().search([
            ('categ_id', '=', accommodation_categ.id),
            ('is_accommodation', '=', True),
        ])
        return request.render('booking_billetweb.accommodation_list', {
            'accommodations': accommodations,
        })

    @http.route('/booking/new', type='http', auth='public', website=True)
    def booking_form(self, product_id=None, **kwargs):
        """Formulaire de réservation"""
        if not product_id:
            return request.redirect('/booking')

        product = request.env['product.template'].sudo().browse(int(product_id))
        if not product.exists() or not product.is_accommodation:
            return request.redirect('/booking')

        return request.render('booking_billetweb.booking_form', {
            'product': product,
        })

    @http.route('/booking/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def booking_submit(self, **post):
        """Traitement du formulaire de réservation"""
        try:
            # Récupération des données
            product_id = int(post.get('product_id'))
            name = post.get('name')
            email = post.get('email')
            phone = post.get('phone', '')
            start_date = datetime.strptime(post.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(post.get('end_date'), '%Y-%m-%d').date()
            notes = post.get('notes', '')

            # Création ou récupération du partenaire
            partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': name,
                    'email': email,
                    'phone': phone,
                })

            # Récupération du produit
            product = request.env['product.template'].sudo().browse(product_id)

            # Création de la réservation
            booking = request.env['booking.reservation'].sudo().create({
                'partner_id': partner.id,
                'product_id': product.id,
                'start_date': start_date,
                'end_date': end_date,
                'nightly_rate': product.nightly_rate,
                'notes': notes,
            })

            # Confirmation automatique (déclenche la création de commande Billetweb)
            booking.action_confirm()

            return request.render('booking_billetweb.booking_confirmation', {
                'booking': booking,
            })

        except Exception as e:
            return request.render('website.404', {
                'error_message': str(e),
            })

    @http.route('/booking/list', type='http', auth='user', website=True)
    def booking_list(self, **kwargs):
        """Liste des réservations du client connecté"""
        partner = request.env.user.partner_id
        bookings = request.env['booking.reservation'].sudo().search([
            ('partner_id', '=', partner.id),
        ], order='create_date desc')

        return request.render('booking_billetweb.booking_list_template', {
            'bookings': bookings,
        })

    @http.route('/booking/webhook/billetweb', type='json', auth='public', csrf=False)
    def billetweb_webhook(self, **kwargs):
        """Webhook pour recevoir les notifications de paiement de Billetweb"""
        try:
            order_id = kwargs.get('order_id')
            status = kwargs.get('status')

            if not order_id:
                return {'status': 'error', 'message': 'Missing order_id'}

            booking = request.env['booking.reservation'].sudo().search([
                ('billetweb_order_id', '=', order_id)
            ], limit=1)

            if not booking:
                return {'status': 'error', 'message': 'Booking not found'}

            # Mise à jour du statut selon la notification Billetweb
            if status == 'paid':
                booking.action_mark_paid()
                return {'status': 'success', 'message': 'Booking marked as paid'}
            elif status == 'cancelled':
                booking.action_cancel()
                return {'status': 'success', 'message': 'Booking cancelled'}

            return {'status': 'success', 'message': 'Status updated'}

        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/booking/availability', type='json', auth='public')
    def check_availability(self, product_id, start_date, end_date, **kwargs):
        """Vérification de la disponibilité en temps réel (AJAX)"""
        try:
            product = request.env['product.template'].sudo().browse(int(product_id))
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()

            available = product.get_availability(start, end)

            # Calcul du prix avec réductions
            delta = end - start
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
                'available': available,
                'nights': nights,
                'subtotal': subtotal,
                'discount_percent': discount,
                'discount_amount': discount_amount,
                'total': total,
            }
        except Exception as e:
            return {'error': str(e)}

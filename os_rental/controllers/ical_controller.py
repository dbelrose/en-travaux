# -*- coding: utf-8 -*-
# os_rental/controllers/ical_controller.py
#
# Expose une URL publique iCal par logement :
#   GET /booking/ical/<product_id>.ics
#
# Cette URL est à coller dans Airbnb et Booking.com comme
# "calendrier externe" pour qu'ils bloquent les dates Odoo.

from odoo import http
from odoo.http import request, Response
import logging

_logger = logging.getLogger(__name__)


class IcalController(http.Controller):

    @http.route('/booking/ical/<int:product_id>.ics',
                type='http', auth='public', csrf=False)
    def export_ical(self, product_id, **kwargs):
        """
        Retourne le calendrier iCal du logement au format text/calendar.

        URL à fournir à Airbnb / Booking.com :
            https://votre-domaine.com/booking/ical/<product_id>.ics

        Le product_id est l'ID Odoo du produit (logement).
        """
        product = request.env['product.template'].sudo().browse(product_id)
        if not product.exists() or not product.is_accommodation:
            return Response('Not found', status=404)

        try:
            ical_content = request.env['booking.reservation'].sudo()\
                ._generate_ical_for_product(product_id)
        except Exception as e:
            _logger.error('Export iCal produit %s : %s', product_id, e)
            return Response('Internal error', status=500)

        return Response(
            ical_content,
            status=200,
            headers={
                'Content-Type':        'text/calendar; charset=utf-8',
                'Content-Disposition': f'attachment; filename="belroseplace-{product_id}.ics"',
                # Pas de cache — les plateformes doivent toujours avoir la version fraîche
                'Cache-Control':       'no-cache, no-store, must-revalidate',
                'Pragma':              'no-cache',
            },
        )

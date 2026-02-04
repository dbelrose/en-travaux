# Fichier: os_airbnb_pdf_import/models/booking_import.py

from odoo import models, fields

import logging

_logger = logging.getLogger(__name__)


class BookingImport(models.Model):
    _inherit = 'booking.import'

    import_type = fields.Selection(
        selection_add=[('email', 'Email')],
        ondelete={'email': 'set default'}
    )

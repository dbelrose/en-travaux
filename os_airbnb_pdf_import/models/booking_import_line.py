# Fichier: os_airbnb_pdf_import/models/booking_import_line.py

from odoo import models, fields


class BookingImportLine(models.Model):
    _inherit = 'booking.import.line'

    import_type = fields.Selection(
        selection_add=[('pdf', 'PDF')],
        ondelete={'pdf': 'set default'}
    )

    origin = fields.Selection(
        selection_add=[('airbnb', 'Airbnb')],
        ondelete={'airbnb': 'set default'}
    )

from odoo import models, fields


class BookingImportLine(models.Model):
    _inherit = 'booking.import.line'

    import_type = fields.Selection(
        selection_add=[('email', 'Email')],
        ondelete={'email': 'set default'}
    )

from odoo import models, fields, api, _


class BookingImport(models.Model):
    _inherit = 'booking.import'

    name = fields.Char(string='Nom', required=True, default='Nouvel import')
    line_count = fields.Integer(string='Nombre de lignes',
                                compute='_compute_line_count')

    @api.depends('booking_line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.booking_line_ids)

    def action_import_airbnb_pdf(self):
        """Action pour ouvrir l'assistant d'import PDF"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importer PDF Airbnb'),
            'view_mode': 'form',
            'res_model': 'airbnb.pdf.importer',
            'target': 'new',
            'context': {'default_import_id': self.id}
        }

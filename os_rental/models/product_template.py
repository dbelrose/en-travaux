from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_accommodation = fields.Boolean(string='Est un logement', compute='_compute_is_accommodation', store=True)
    nightly_rate = fields.Float(string='Tarif par nuit')
    max_occupancy = fields.Integer(string='Capacité maximum')
    booking_ids = fields.One2many('booking.reservation', 'product_id', string='Réservations')

    @api.depends('categ_id')
    def _compute_is_accommodation(self):
        accommodation_categ = self.env.ref('os_hospitality_managment.product_category_tdsmdt', raise_if_not_found=False)
        for product in self:
            product.is_accommodation = accommodation_categ and product.categ_id == accommodation_categ

    def get_availability(self, start_date, end_date):
        """Vérifie la disponibilité du logement pour une période"""
        self.ensure_one()
        overlapping = self.env['booking.reservation'].search([
            ('product_id', '=', self.id),
            ('state', 'in', ['draft', 'confirmed', 'paid']),
            ('start_date', '<', end_date),
            ('end_date', '>', start_date),
        ])
        return len(overlapping) == 0

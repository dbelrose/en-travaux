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

    def get_availability(self, start_date, end_date, exclude_booking_id=None):
        """
        Vérifie la disponibilité du logement pour une période

        Args:
            start_date: Date de début
            end_date: Date de fin
            exclude_booking_id: ID de réservation à exclure (pour modification)
        """
        self.ensure_one()
        domain = [
            ('product_id', '=', self.id),
            ('state', 'in', ['confirmed', 'payment_sent', 'paid']),  # Exclure draft et cancelled
            ('start_date', '<', end_date),
            ('end_date', '>', start_date),
        ]

        if exclude_booking_id:
            domain.append(('id', '!=', exclude_booking_id))

        overlapping = self.env['booking.reservation'].search(domain)
        return len(overlapping) == 0

    def get_booking_calendar_data(self, start_date, end_date):
        """
        Récupère les données pour afficher le calendrier de disponibilité

        Returns:
            Liste de dictionnaires avec les périodes occupées
        """
        self.ensure_one()
        bookings = self.env['booking.reservation'].search([
            ('product_id', '=', self.id),
            ('state', 'in', ['confirmed', 'payment_sent', 'paid']),
            ('start_date', '<=', end_date),
            ('end_date', '>=', start_date),
        ])

        calendar_data = []
        for booking in bookings:
            calendar_data.append({
                'id': booking.id,
                'name': booking.name,
                'start': booking.start_date.isoformat(),
                'end': booking.end_date.isoformat(),
                'partner': booking.partner_id.name,
                'state': booking.state,
                'color': self._get_booking_color(booking.state),
            })

        return calendar_data

    def _get_booking_color(self, state):
        """Retourne une couleur selon l'état de la réservation"""
        colors = {
            'draft': '#6c757d',
            'confirmed': '#17a2b8',
            'payment_sent': '#ffc107',
            'paid': '#28a745',
            'cancelled': '#dc3545',
        }
        return colors.get(state, '#6c757d')

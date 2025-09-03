# Extension du modèle account.move pour les factures hospitality

from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    # Lien vers le mois de réservation pour les factures clients
    booking_month_id = fields.Many2one(
        'booking.month',
        string="Mois de réservation",
        help="Mois de réservation associé à cette facture"
    )

    # Champ pour identifier les factures d'hospitality
    is_hospitality_invoice = fields.Boolean(
        string="Facture Hospitality",
        compute='_compute_is_hospitality_invoice',
        store=True
    )

    @api.depends('booking_month_id')
    def _compute_is_hospitality_invoice(self):
        for record in self:
            record.is_hospitality_invoice = bool(record.booking_month_id)

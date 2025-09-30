from odoo import models, fields

class AccountMove(models.Model):
    _inherit = 'account.move'

    billetweb_payout_id = fields.Many2one(
        'billetweb.payout', string="Virement BilletWeb"
    )

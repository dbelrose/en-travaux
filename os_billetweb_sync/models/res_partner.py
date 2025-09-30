from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    billetweb_payout_ids = fields.One2many(
        'billetweb.payout', 'partner_id',
        string="Virements BilletWeb"
    )

    billetweb_invoice_ids = fields.One2many(
        'account.move', 'partner_id',
        domain="[('billetweb_payout_id', '!=', False)]",
        string="Factures BilletWeb"
    )

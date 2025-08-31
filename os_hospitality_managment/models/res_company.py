from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    incoterm_id = fields.Many2one('account.incoterms', string='Default incoterm',
                                  help='International Commercial Terms are a series of predefined commercial terms '
                                       'used in international transactions.')

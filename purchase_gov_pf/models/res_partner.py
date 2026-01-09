# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class res_partner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    customer_supplier_ref = fields.Char('Customer supplier ref.', company_dependent=True,
                                        help="Code client utilisé chez le fournisseur")

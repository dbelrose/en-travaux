# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    signature_delegation_threshold = fields.Monetary(
        string='Signature delegation threshold')

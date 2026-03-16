# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class SurveyQuestion(models.Model):

    _inherit = "survey.question"

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id
    )
    code = fields.Char("Code")

from odoo import fields, models


class SurveyUserInputLine(models.Model):
    _inherit = 'survey.user_input.line'

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id
    )
    input_date = fields.Datetime(
        string='Date',
        related='user_input_id.input_date',
        readonly=True,
        store=True
    )

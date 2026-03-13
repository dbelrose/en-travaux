from odoo import fields, models

class SurveyQuestionAnswer(models.Model):
    _inherit = "survey.question.answer"

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id
    )

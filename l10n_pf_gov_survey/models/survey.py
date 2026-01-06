# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import werkzeug

from odoo import fields, models, api
from datetime import datetime


class Survey(models.Model):

    _inherit = "survey.survey"

    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id
    )
    # private = fields.Boolean("Privé", default=True)
    code = fields.Char("Code")

    @api.model
    def create(self, vals):
        survey = super(Survey, self).create(vals)

        # Année

        annee = datetime.now().year
        anneec = str(annee)

        question = self.env['survey.question'].create({
            'code': 'ANNEE',
            'constr_mandatory': False,
            'is_conditional': False,
            'is_time_limited': False,
            'question_type': 'simple_choice',
            'sequence': 0,
            'survey_id': survey.id,
            'company_id': survey.company_id.id,
            'title': 'Année'
        })
        self.env['survey.question.answer'].create({
            'question_id': question.id,
            'sequence': annee,
            'value': anneec,
            'company_id': question.company_id.id,
        })

        # Mois

        mois = datetime.now().month
        moisc = datetime.now().strftime('%B')

        question = self.env['survey.question'].create({
            'code': 'MOIS',
            'constr_mandatory': False,
            'is_conditional': False,
            'is_time_limited': False,
            'question_type': 'simple_choice',
            'sequence': 0,
            'survey_id': survey.id,
            'company_id': survey.company_id.id,
            'title': 'Mois'
        })
        self.env['survey.question.answer'].create({
            'question_id': question.id,
            'sequence': mois,
            'value': moisc,
            'company_id': question.company_id.id,
        })

        # Nom

        current_user_name = self.env.user.name
        current_user_id = self.env.uid

        question = self.env['survey.question'].create({
            'code': 'NOM',
            'constr_mandatory': False,
            'is_conditional': False,
            'is_time_limited': False,
            'question_type': 'simple_choice',
            'sequence': 0,
            'survey_id': survey.id,
            'company_id': survey.company_id.id,
            'title': 'Nom'
        })
        self.env['survey.question.answer'].create({
            'question_id': question.id,
            'sequence': current_user_id,
            'value': current_user_name,
            'company_id': question.company_id.id,
        })

        return survey

    def action_start_survey(self, answer=None):
        """ Open the website page with the survey form """
        self.ensure_one()
        url = '%s?%s' % (self.get_start_url(), werkzeug.urls.url_encode({'answer_token': answer and answer.access_token or None}))
        return {
            'type': 'ir.actions.act_url',
            'name': "Start Survey",
            'target': 'new',
            'url': url,
        }

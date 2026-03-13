import uuid

from odoo import fields, models, api
from datetime import datetime


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    input_year = fields.Integer(
        group_operator="count_distinct",
        string="Année",
        readonly=True,
        store=True,
        compute="_compute_input_year",
    )
    input_date = fields.Datetime(
        string="Date",
        readonly=False,
        store=True,
        compute="_compute_input_date",
    )
    company_id = fields.Many2one(
        "res.company",
        "Company",
        default=lambda self: self.env.user.company_id.id,
    )
    imported = fields.Boolean(
        'Importé',
        default=False,
    )
    access_token = fields.Char(
        'Identification token',
        default=lambda self: str(uuid.uuid4()),
        readonly=False,
        required=False,
        copy=False,
    )
    survey_id = fields.Many2one(
        'survey.survey',
        string='Survey',
        required=True,
        readonly=False,
        ondelete='cascade',
    )
    state = fields.Selection([
        ('new', 'Not started yet'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed')],
        string='Status',
        default='new',
        readonly=False
    )

    @api.depends('imported')
    def _compute_input_date(self):
        for user_input in self:
            if not user_input.imported:
                user_input.input_date = fields.Datetime.now()

    @api.depends('input_date')
    def _compute_input_year(self):
        for user_input in self:
            if user_input.input_date:
                user_input.input_year = user_input.input_date.year

    @api.model
    def create(self, vals):
        input_year = datetime.now().year
        mois = datetime.now().month
        moisc = datetime.now().strftime('%B')

        if vals.get('imported'):
            if vals.get('input_date'):
                input_year = fields.Datetime.from_string(vals.get('input_date')).year
                mois = fields.Datetime.from_string(vals.get('input_date')).month
                moisc = fields.Datetime.from_string(vals.get('input_date')).strftime('%B')
            current_user_name = vals.get('nickname')
            # if self.env['res.users'].search_count([('name', '=', current_user_name)]) == 1:
            #     current_user_id = self.env['res.users'].search_count([('name', '=', current_user_name)]).id
            # else:
            #     current_user_id = 9999
        else:
            current_user_name = self.env.user.name
            # current_user_id = self.env.uid

        userinput = super(SurveyUserInput, self).create(vals)

        # Année

        # Création de la réponse suggérée si elle n'existe pas encore

        input_yearc = str(input_year)

        question = self.env['survey.question'].search([
            ('survey_id', '=', userinput.survey_id.id),
            ('code', '=', 'ANNEE')
        ])
        answer = self.env['survey.question.answer'].search([
            ('company_id', '=', question.company_id.id),
            ('question_id', '=', question.id),
            ('value', '=', input_yearc),
            ('sequence', '=', input_year)
        ])

        if not answer:
            answer = self.env['survey.question.answer'].create({
                'question_id': question.id,
                'value': input_yearc,
                'sequence': input_year,
                'company_id': question.company_id.id,
            })

        # Création de la réponse si elle n'existe pas encore

        input_line = self.env['survey.user_input.line'].search([
            ('question_id', '=', question.id),
            ('user_input_id', '=', userinput.id)
        ])

        if not input_line:
            self.env['survey.user_input.line'].create({
                'answer_type': 'suggestion',
                'company_id': question.company_id.id,
                'question_id': question.id,
                'survey_id': question.survey_id.id,
                'user_input_id': userinput.id,
                'suggested_answer_id': answer.id
            })
        else:
            userinput.write({"state": 'done'})

        # Mois

        # Création de la réponse suggérée si elle n'existe pas encore

        question = self.env['survey.question'].search([
            ('survey_id', '=', userinput.survey_id.id),
            ('code', '=', 'MOIS')
        ])

        answer = self.env['survey.question.answer'].search([
            ('company_id', '=', question.company_id.id),
            ('question_id', '=', question.id),
            ('value', '=', moisc),
            ('sequence', '=', mois)
        ])

        if not answer:
            answer = self.env['survey.question.answer'].create({
                'question_id': question.id,
                'value': moisc,
                'sequence': mois,
                'company_id': question.company_id.id,
            })

        # Création de la réponse si elle n'existe pas encore

        input_line = self.env['survey.user_input.line'].search([
            ('question_id', '=', question.id),
            ('user_input_id', '=', userinput.id)
        ])

        if not input_line:
            self.env['survey.user_input.line'].create({
                'answer_type': 'suggestion',
                'company_id': question.company_id.id,
                'question_id': question.id,
                'survey_id': question.survey_id.id,
                'user_input_id': userinput.id,
                'suggested_answer_id': answer.id
            })

        # Nom

        # Création de la réponse suggérée si elle n'existe pas encore

        question = self.env['survey.question'].search([
            ('survey_id', '=', userinput.survey_id.id),
            ('code', '=', 'NOM')
        ])

        answer = self.env['survey.question.answer'].search([
            ('company_id', '=', question.company_id.id),
            ('question_id', '=', question.id),
            ('value', '=', current_user_name),
            # ('sequence', '=', current_user_id)
        ])

        if not answer:
            answer = self.env['survey.question.answer'].create({
                'question_id': question.id,
                'value': current_user_name,
                # 'sequence': current_user_id,
                'company_id': question.company_id.id,
            })

        # Création de la réponse si elle n'existe pas encore

        input_line = self.env['survey.user_input.line'].search([
            ('question_id', '=', question.id),
            ('user_input_id', '=', userinput.id)
        ])

        if not input_line:
            self.env['survey.user_input.line'].create({
                'answer_type': 'suggestion',
                'company_id': question.company_id.id,
                'question_id': question.id,
                'survey_id': question.survey_id.id,
                'user_input_id': userinput.id,
                'suggested_answer_id': answer.id
            })

        return userinput

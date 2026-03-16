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
    # Redéclaration pour autoriser l'édition lors de l'import
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
        readonly=False,
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

    @api.model_create_multi
    def create(self, vals_list):
        userinputs = super(SurveyUserInput, self).create(vals_list)

        for userinput in userinputs:
            # Détermination de l'année, du mois et du nom selon l'import ou non
            if userinput.imported and userinput.input_date:
                input_year = userinput.input_date.year
                mois = userinput.input_date.month
                moisc = userinput.input_date.strftime('%B')
                current_user_name = userinput.nickname or self.env.user.name
            else:
                input_year = datetime.now().year
                mois = datetime.now().month
                moisc = datetime.now().strftime('%B')
                current_user_name = self.env.user.name

            input_yearc = str(input_year)

            # --- ANNEE ---
            question = self.env['survey.question'].search([
                ('survey_id', '=', userinput.survey_id.id),
                ('code', '=', 'ANNEE')
            ])
            if question:
                answer = self.env['survey.question.answer'].search([
                    ('company_id', '=', question.company_id.id),
                    ('question_id', '=', question.id),
                    ('value', '=', input_yearc),
                    ('sequence', '=', input_year),
                ])
                if not answer:
                    answer = self.env['survey.question.answer'].create({
                        'question_id': question.id,
                        'value': input_yearc,
                        'sequence': input_year,
                        'company_id': question.company_id.id,
                    })

                input_line = self.env['survey.user_input.line'].search([
                    ('question_id', '=', question.id),
                    ('user_input_id', '=', userinput.id),
                ])
                if not input_line:
                    self.env['survey.user_input.line'].create({
                        'answer_type': 'suggestion',
                        'company_id': question.company_id.id,
                        'question_id': question.id,
                        'survey_id': question.survey_id.id,
                        'user_input_id': userinput.id,
                        'suggested_answer_id': answer.id,
                    })
                else:
                    userinput.write({"state": 'done'})

            # --- MOIS ---
            question = self.env['survey.question'].search([
                ('survey_id', '=', userinput.survey_id.id),
                ('code', '=', 'MOIS')
            ])
            if question:
                answer = self.env['survey.question.answer'].search([
                    ('company_id', '=', question.company_id.id),
                    ('question_id', '=', question.id),
                    ('value', '=', moisc),
                    ('sequence', '=', mois),
                ])
                if not answer:
                    answer = self.env['survey.question.answer'].create({
                        'question_id': question.id,
                        'value': moisc,
                        'sequence': mois,
                        'company_id': question.company_id.id,
                    })

                input_line = self.env['survey.user_input.line'].search([
                    ('question_id', '=', question.id),
                    ('user_input_id', '=', userinput.id),
                ])
                if not input_line:
                    self.env['survey.user_input.line'].create({
                        'answer_type': 'suggestion',
                        'company_id': question.company_id.id,
                        'question_id': question.id,
                        'survey_id': question.survey_id.id,
                        'user_input_id': userinput.id,
                        'suggested_answer_id': answer.id,
                    })

            # --- NOM ---
            question = self.env['survey.question'].search([
                ('survey_id', '=', userinput.survey_id.id),
                ('code', '=', 'NOM')
            ])
            if question:
                answer = self.env['survey.question.answer'].search([
                    ('company_id', '=', question.company_id.id),
                    ('question_id', '=', question.id),
                    ('value', '=', current_user_name),
                ])
                if not answer:
                    answer = self.env['survey.question.answer'].create({
                        'question_id': question.id,
                        'value': current_user_name,
                        'company_id': question.company_id.id,
                    })

                input_line = self.env['survey.user_input.line'].search([
                    ('question_id', '=', question.id),
                    ('user_input_id', '=', userinput.id),
                ])
                if not input_line:
                    self.env['survey.user_input.line'].create({
                        'answer_type': 'suggestion',
                        'company_id': question.company_id.id,
                        'question_id': question.id,
                        'survey_id': question.survey_id.id,
                        'user_input_id': userinput.id,
                        'suggested_answer_id': answer.id,
                    })

        return userinputs
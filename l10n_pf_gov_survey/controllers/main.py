# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
import werkzeug

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import fields, http, SUPERUSER_ID, _
from odoo.addons.base.models.ir_ui_view import keep_query
from odoo.exceptions import UserError
from odoo.http import request, content_disposition
from odoo.osv import expression
from odoo.tools import format_datetime, format_date, is_html_empty

from odoo.addons.web.controllers.main import Binary

_logger = logging.getLogger(__name__)


class Survey(http.Controller):


    # ------------------------------------------------------------
    # REPORTING SURVEY ROUTES AND TOOLS
    # ------------------------------------------------------------

    @http.route('/survey/results/<model("survey.survey"):survey>', type='http', auth='user', website=True)
    def survey_report(self, survey, answer_token=None, **post):
        """ Display survey Results & Statistics for given survey.

        New structure: {
            'survey': current survey browse record,
            'question_and_page_data': see ``SurveyQuestion._prepare_statistics()``,
            'survey_data'= see ``SurveySurvey._prepare_statistics()``
            'search_filters': [],
            'search_finished': either filter on finished inputs only or not,
        }
        """
        user_input_lines, search_filters = self._extract_filters_data(survey, post)
        survey_data = survey._prepare_statistics(user_input_lines)
        question_and_page_data = survey.question_and_page_ids._prepare_statistics(user_input_lines)

        template_values = {
            # survey and its statistics
            'survey': survey,
            'question_and_page_data': question_and_page_data,
            'survey_data': survey_data,
            # search
            'search_filters': search_filters,
            'search_finished': post.get('finished') == 'true',
        }

        if survey.session_show_leaderboard:
            template_values['leaderboard'] = survey._prepare_leaderboard_values()

        return request.render('survey.survey_page_statistics', template_values)


    def _extract_filters_data(self, survey, post):
        search_filters = []
        line_filter_domain, line_choices = [], []
        for data in post.get('filters', '').split('|'):
            try:
                row_id, answer_id = (int(item) for item in data.split(','))
            except:
                pass
            else:
                if row_id and answer_id:
                    line_filter_domain = expression.AND([
                        ['&', ('matrix_row_id', '=', row_id), ('suggested_answer_id', '=', answer_id)],
                        line_filter_domain
                    ])
                    answers = request.env['survey.question.answer'].browse([row_id, answer_id])
                elif answer_id:
                    line_choices.append(answer_id)
                    answers = request.env['survey.question.answer'].browse([answer_id])
                if answer_id:
                    question_id = answers[0].matrix_question_id or answers[0].question_id
                    search_filters.append({
                        'question': question_id.title,
                        'answers': '%s%s' % (answers[0].value, ': %s' % answers[1].value if len(answers) > 1 else '')
                    })
        if line_choices:
            line_filter_domain = expression.AND([[('suggested_answer_id', 'in', line_choices)], line_filter_domain])

        user_input_domain = self._get_user_input_domain(survey, line_filter_domain, **post)
        user_input_lines = request.env['survey.user_input'].sudo().search(user_input_domain).mapped('user_input_line_ids')

        return user_input_lines, search_filters

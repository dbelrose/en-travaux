# -*- coding: utf-8 -*-
{
    'name': 'PF: GOV: Sondage',
    'version': '1.0',
    'category': 'French Polynesian localization',
    'description': u"""
Localisation du module Sondage
""",
    'author': 'Didier Belrose',
	'maintainer': 'Didier Belrose',
	'company': 'Polynésie française',
    'depends': [
        'base',
        'survey',
    ],
    'data': [
        'views/survey_question.xml',
        'views/survey_question_answer.xml',
        'views/survey.xml',
        'views/user_input_line.xml',
        'views/user_input.xml',
        # 'views/survey_templates_statistics.xml',

        'security/survey_question.xml',
        'security/survey_question_answer.xml',
        'security/survey_survey.xml',
        'security/survey_user_input.xml',
        'security/survey_user_input_line.xml',

    ],
	'images': [
		'static/description/icon.png',
	],
    'license': 'AGPL-3',
	'installable': True,
    'application': True,
}

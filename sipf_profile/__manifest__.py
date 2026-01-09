# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': "SIPF Profile",

    'summary': '',
    'description': """
Ce module permet de personnaliser Odoo pour le SIPF
""",
    'author': 'INVITU, Cyril VINH-TUNG',
    'website': 'http://www.invitu.com',

    'category': 'Custom',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'gov_pf_profile',
        'budget_gov_pf',
        'purchase_project_gov_pf',
    ],

    # always loaded
    'data': [
        'data/ir_sequence_data.xml',
        'data/hr_department_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}

# -*- coding: utf-8 -*-
{
    'name': 'PF: GOV: DSI',
    'version': '1.0',
    'category': 'French Polynesian localization',
    'description': u"""
Service de l'informatique de la polynésie française
""",
    'author': 'Didier Belrose',
    'maintainer': 'Didier Belrose',
    'company': 'Polynésie française',
    'depends': [
        'l10n_pf_gov_mef',
    ],
    'data': [
        'data/res_partner_data.xml',

        'security/ir_module_category_data.xml',
        'security/res_groups_data.xml',

        'data/res_company_data.xml',
        'data/ir_mail_server_data.xml',
        'data/res_users_data.xml',
        'data/res_company_ldap_data.xml',

        'views/external_layout_custom.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    'license': 'AGPL-3',
    'installable': True,
    'application': True,
}

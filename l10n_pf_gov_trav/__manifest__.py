# -*- coding: utf-8 -*-
{
    'name': 'PF: GOV: TRAV',
    'version': '18.0.1.0.0',
    'category': 'French Polynesian localization',
    'description': u"""
Direction du travail de la polynésie française
""",
    'author': 'Didier Belrose',
    'maintainer': 'Didier Belrose',
    'company': 'Polynésie française',
    'depends': [
        'l10n_pf_gov_mea',
    ],
    'data': [
        'data/res_partner_data.xml',

        'security/ir_module_category_data.xml',
        'security/res_groups_data.xml',

        'data/res_company_data.xml',
        'data/ir_mail_server_data.xml',
        'data/res_users_data.xml',
        'data/res_company_ldap_data.xml',
        # ir_property_data.xml supprimé : le modèle ir.property
        # n'existe plus en v17+. Voir notes de migration ci-dessous.
    ],
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'license': 'AGPL-3',
    'application': True,
}
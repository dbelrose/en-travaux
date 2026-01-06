# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'DHV',
    'summary': 'Specific profil of DHV',
    'description': """
    Application de suivi des demandes du Pil
     DHV of French Polynesia and all it's specificities
""",
    'version': '1.0',
    'category': 'production',
    'author': 'DSI, Didier Belrose, Félix Chenon',
    "website": "https://gitlab.gov.pf/odoo/addons/-/tree/master/sources/dhv_pil",
    'depends': [
        'crm',
        'mail',
        'board',
        'web_domain_field',
        'l10n_pf_gov_dhv',
        'referentiel',
    ],
    'data': [
        'security/pilinfo_security.xml',
        'security/ir.model.access.csv',
        'views/pil_menu.xml',
        'views/pil_demande_view.xml',
        'views/pil_parametrage.xml',
        'views/pil_rapport_view.xml'
#        'views/dashboard_view.xml'
    ],
    'images': ['static/description/icon.png'],
    'license': 'AGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False
}

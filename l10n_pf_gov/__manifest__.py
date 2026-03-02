# -*- coding: utf-8 -*-
{
    'name': 'PF: GOV',
    'version': '18.0.1.0.0',
    'category': 'French Polynesian localization',
    'description': u"""
Gouvernement de la polynésie française
""",
    'author': 'Didier Belrose',
    'maintainer': 'Didier Belrose',
    'company': 'Polynésie française',
    'depends': [
        'auth_ldap',  #
        # 'auth_oauth',
        # 'auth_oauth_keycloak',
        'board',  # Tableau de bord
        'calendar',  # Calendrier
        'contacts',  # Contacts
        'crm_security_group', # CRM Only Security Groups
        'l10n_fr',  # Comptabilité France
        'l10n_fr_naf_ape',  # Classification française de entreprises
        'l10n_pf',  # Polynésie française
        'purchase_security',  # Purchase Order security
        'res_company_code',
        'survey',  # Sondage
        # 'users_ldap_groups',  #
    ],
    'data': [
        'security/ir_module_category_data.xml',
        'security/res_groups_data.xml',
        'security/ir.model.access.csv',

        'data/ir_cron_data.xml',
        'data/mail_template_data.xml',
        # 'data/ir_config_parameter_data.xml', cleaning
        'data/res_partner_data.xml',
        'data/res_company.xml',
        'data/res_groups_data.xml',
        # 'data/auth_oauth_provider_data.xml',
        
        'data/res.users.csv',

        'views/res_users.xml',
        'views/res_config_settings.xml'
    ],
    'images': [
        'static/description/icon.png',
    ],
    'license': 'AGPL-3',
    'auto_install': False,
    'installable': True,
    'application': True,
}

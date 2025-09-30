{
    'name': "BilletWeb Sync",
    'version': '17.0.1.0.0',
    'depends': [
        'os_base',
        'os_billetweb_import',
        'partner_multi_relation',
    ],
    'category': 'Accounting',
    'summary': 'Intégration API BilletWeb : virements, paiements et commissions',
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'data': [
        'security/ir.model.access.csv',

        'views/billetweb_api_attendees_views.xml',
        'views/billetweb_api_call_views.xml',
        'views/billetweb_api_payout_details_views.xml',
        'views/billetweb_api_payouts_views.xml',
        'views/billetweb_import_views.xml',
        'views/billetweb_import_history_views.xml',
        'views/billetweb_payout_views.xml',
        'views/account_move_filter_billetweb.xml',
        'views/res_partner_view.xml',
        'views/action_views.xml',
        'views/billetweb_import_wizard_views.xml',
        'views/menu_views.xml',

        'data/billetweb_cron.xml',
        'data/mail_template_billetweb_import.xml',

        'views/action_views.xml',

        'views/menu_views.xml',
    ],
    'license': 'LGPL-3',
    'application': True,
    'installable': True,
    'auto_install': False,
}

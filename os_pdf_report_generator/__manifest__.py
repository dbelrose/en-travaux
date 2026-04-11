{
    'name': "PDF Report Generator",

    'summary': """
        Generate your Report with PDF template""",

    'description': """
        Simple module to generate report with PDF template.
        Includes print credit management per company, with alerts and manual replenishment via sale orders.
    """,

    'author': "OpalSea",

    'maintainers': ["OpalSea"],

    'website': "",

    'images': ["static/description/banner.png"],

    'category': 'Technical',

    'version': '17.0.2.0.0',

    'application': True,

    'installable': True,

    'depends': ['base', 'mail', 'sale', 'account', 'website_sale'],

    'pre_init_hook': 'pre_init_hook',

    'data': [
        'security/ir.model.access.csv',

        'data/product_data.xml',

        'views/pdf_print_credit_wizard_view.xml',
        'views/res_company_view.xml',
        'views/pdf_report_config_view.xml',
        'views/ir_action_report_view.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'os_pdf_report_generator/static/src/js/report/action_manager_report.esm.js'
        ]
    },

    'license': 'LGPL-3',

    'external_dependencies': {
        'python': ['pdfrw'],
    }
}

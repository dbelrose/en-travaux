{
    'name': "PDF Report Generator",

    'summary': """
        Generate your Report with PDF template""",

    'description': """
        Simple module to generate report with PDF template
    """,

    'author': "OpalSea",
    
    'maintainers': ["OpalSea"],

    'website': "",
    
    'images': ["static/description/banner.png"],

    'category': 'Technical',
    
    'version': '17.0.1.0.0',
        
    'application': True,
    
    'installable': True,

    'depends': ['base', 'mail'],

    'data': [
        'security/ir.model.access.csv',

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

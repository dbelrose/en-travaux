{
    'name': 'Booking Manager',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Booking manager',
    'description': 'Booking Manager',
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'product',
        'contacts',
        'event',
        'l10n_pf',
        'os_base',
        'product',
    ],
    'external_dependencies': {
        'python': [
            'pandas',
            'openpyxl',
            'num2words',
        ],
    },
    'data': [
        # Sécurité
        'security/ir.model.access.csv',
        
        # Vues des wizards
        'views/booking_wizards_views.xml',
        
        # Vues des modèles principaux
        'views/booking_import_views.xml',
        'views/booking_import_line_views.xml',

        # Menus
        'views/menu_views.xml',
        
        # Données initiales
        'data/account_tax_group_data.xml',
        'data/account_tax_data.xml',
        'data/product_category_data.xml',
        'data/product_template_data.xml',

        'data/res_partner_category_data.xml',
        'data/res_partner_data.xml',
    ],
    'images': [
        'static/description/icon.png',
    ],
    
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 10,
}

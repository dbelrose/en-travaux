{
    'name': 'Hospitality Management Base',
    'version': '17.0.1.0.0',
    'summary': 'Base OpalSea module',
    'description': 'This module contain OpalSea modules common dependencies',
    'category': 'Accounting',
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'license': 'LGPL-3',
    'depends': [
        'account',
        'base',
        'contacts',
        'partner_employee_quantity',
        'partner_firstname',
        'partner_identification',
        'partner_multi_relation',
        'product',
    ],
    'data': [
        'data/partner_relation_type_data.xml',
        'data/partner_id_category_data.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False
}

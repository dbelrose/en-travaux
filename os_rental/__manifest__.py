{
    'name': 'Réservation Logement avec Billetweb',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Gestion des réservations de logements avec paiement Billetweb',
    'depends': ['base', 'product', 'website', 'queue_job'],
    'data': [
        'security/ir.model.access.csv',
        'data/booking_config_data.xml',
        'views/booking_config_views.xml',
        'views/product_template_views.xml',
        'views/booking_views.xml',
        'views/website_booking_templates.xml',
        'data/email_templates.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

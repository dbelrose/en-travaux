{
    'name': 'Réservation Logement avec Billetweb',
    'version': '17.0.3.0.0',
    'author': 'OpalSea',
    'category': 'Sales',
    'summary': 'Gestion des réservations de logements avec paiement Billetweb',
    'depends': ['base', 'product', 'website', 'queue_job', 'mail', 'account'],
    'data': [
        # Templates email — doivent être chargés AVANT les données qui y font référence
        'data/mail_templates.xml',
        'data/mail_template_paid.xml',
        # Séquences et config
        'security/ir.model.access.csv',
        'data/booking_config_data.xml',
        # Tâche planifiée
        'data/cron_data.xml',
        'data/cron_ical_data.xml',
        # Vues
        'views/assets.xml',
        'views/product_template_views.xml',
        'views/booking_views.xml',
        'views/website_booking_templates.xml',
        'views/res_config_settings_views.xml',
        'views/booking_ical_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}

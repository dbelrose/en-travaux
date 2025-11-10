# -*- coding: utf-8 -*-

{
    'name': 'Billetweb Payment Provider',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Payment Provider: Billetweb',
    'description': """
Billetweb Payment Provider
===========================

Module d'intégration Billetweb comme processeur de paiement pour Odoo.

Fonctionnalités:
- Création de commandes de paiement via l'API Billetweb
- Gestion des transactions et des statuts de paiement
- Support des remboursements
- Synchronisation des événements Billetweb
    """,
    'author': 'Your Company',
    'website': 'https://www.billetweb.fr',
    'license': 'LGPL-3',
    'depends': [
        'payment',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_billetweb_templates.xml',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'assets': {
        'web.assets_frontend': [
            'payment_billetweb/static/src/js/payment_form.js',
            'payment_billetweb/static/src/scss/payment_form.scss',
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
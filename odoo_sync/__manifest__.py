{
    'name': 'Odoo.com Database Sync',
    'version': '14.0.1.0.0',
    'category': 'Tools',
    'summary': 'Synchronise les bases de données depuis odoo.com',
    'description': """
        Module pour télécharger automatiquement les bases de données
        depuis un compte odoo.com vers une instance on-premise.
    """,
    'author': 'Didier BELROSE (DSI)',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/odoo_sync_config_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}

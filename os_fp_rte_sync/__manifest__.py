{
    'name': 'RTE Sync - Synchronisation Répertoire des Entreprises (PF)',
    'version': '17.0.1.0.0',
    'category': 'Contacts',
    'summary': 'Synchronisation du Répertoire des Entreprises de Polynésie française',
    'description': """
Synchronisation RTE (ISPF)
==========================
Ce module permet de synchroniser automatiquement les données du Répertoire 
des Entreprises (RTE) de l'ISPF (Polynésie française) avec les contacts Odoo.

Fonctionnalités :
-----------------
* Import automatique des entreprises depuis data.gouv.fr
* Gestion des établissements multiples
* Catégorisation par code NAF/APE
* Classification par effectifs
* Formes juridiques françaises
* Numéros d'identification TAHITI et RTE_ETAB
* Détection automatique des nouvelles versions du fichier
* Import incrémentiel avec gestion des modifications
* Archivage automatique des entreprises radiées

Référentiels inclus :
---------------------
* Codes APE/NAF avec libellés complets
* Formes juridiques françaises (110 à 990)
* Classes d'effectifs standardisées
    """,
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'contacts',
        'queue_job',
        'partner_company_type',  # OCA partner-contact
        'partner_identification',  # OCA partner-contact
        'partner_employee_quantity',  # OCA partner-contact (optionnel)
    ],
    'data': [
        'security/rte_sync_security.xml',
        'security/ir.model.access.csv',

        'data/partner_categories.xml',
        'data/partner_company_type_data.xml',
        'data/res.partner.category.csv',
        'data/res.partner.employee_quantity_range.csv',
        'data/ir_cron.xml',
        'data/ir_config_parameter.xml',
        # 'data/queue_job_channel.xml',

        'views/rte_sync_views.xml',
        'views/res_config_settings_view.xml',
        'views/partner_image_wizard_views.xml',
        'views/res_partner_image_cache_wizard.xml',
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    'installable': True,
    'application': False,
    'auto_install': False,
}
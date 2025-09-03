{
    'name': 'Booking.com Import Manager',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Import et gestion des réservations Booking.com avec génération automatique de factures',
    'description': """
Booking.com Import Manager
==========================

Ce module permet de gérer les réservations Booking.com de deux façons :

**Import de fichiers Excel**
* Import automatique des fichiers exportés depuis Booking.com
* Prévisualisation des données avant import
* Validation et nettoyage automatique des données

**Saisie manuelle**
* Création manuelle d'enregistrements de réservation
* Interface utilisateur simplifiée
* Validation des données en temps réel

**Fonctionnalités principales**
* Calcul automatique des taxes de séjour
* Génération automatique des factures (mairie, concierge, Booking.com)
* Gestion des clients et partenaires
* Rapports et statistiques détaillés
* Interface mobile-friendly

**Calculs automatiques**
* Nuitées par trimestre et par mois
* Taxes de séjour (60 XPF par nuitée adulte)
* Commissions Booking.com
* Exemptions pour enfants de 12 ans et moins

**Factures générées**
* Factures mairie pour taxes de séjour
* Factures concierge pour commissions
* Factures Booking.com pour commissions

**Compatibilité**
* Odoo 16.0+
* Format Excel Booking.com standard
* Multi-sociétés
    """,
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'account',
        'product',
        'contacts',
        'event',
        'l10n_pf',
        'os_base',
        'product',
        'web',
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

        # Product views
        'views/product_template_views.xml',
        'views/product_pricelist_views.xml',
        'views/product_pricelist_item_views.xml',

        # Vues des wizards
        'views/booking_wizards_views.xml',
        'views/hospitality_config_wizard_views.xml',
        'views/customer_invoice_wizard_view.xml',

        # Vues des modèles principaux
        'views/booking_import_views.xml',
        'views/booking_month_views.xml',
        'views/booking_month_views_update.xml',
        'views/booking_month_context_buttons.xml',
        'views/booking_quarter_views.xml',
        'views/booking_wizards_views.xml',
        'views/booking_import_line_views.xml',

        # Reports
        'reports/customer_invoice_report.xml',

        # Menus
        'views/menu_views.xml',
        'views/menu_customer_invoices.xml',
        
        # Données initiales
        'data/account_account_data.xml',
        'data/account_tax_group_data.xml',
        'data/account_tax_data.xml',
        'data/product_category_data.xml',
        'data/product_template_data.xml',

        'data/res_partner_category_data.xml',
        'data/res_partner_data.xml',
        'data/res_partner_relation_type_data.xml',

        'data/product_pricelist_data.xml',
        'data/product_pricelist_item_data.xml',

        'data/customer_invoice_data.xml',
    ],
    # 'assets': {
        # 'web.assets_backend': [
            # CSS pour l'interface backend (dashboard, vues, widgets)
            # 'os_hospitality_managment/static/src/css/hospitality_dashboard.css',
            # 'os_hospitality_managment/static/src/css/booking_views.css',
            # JavaScript pour les interactions et widgets personnalisés
            # 'os_hospitality_managment/static/src/js/booking_widgets.js',
        # ],
        # 'web.report_assets_common': [
            # CSS pour tous les types de rapports (écran et impression)
        #     'os_hospitality_managment/static/src/css/hospitality_reports.css',
        # ],
        # 'web.report_assets_pdf': [
            # CSS spécifique aux rapports PDF (optimisations impression)
        #     'os_hospitality_managment/static/src/css/hospitality_invoice_pdf.css',
        # ],
        # 'web.assets_frontend': [
            # CSS pour le portail client (interface publique)
    #         'os_hospitality_managment/static/src/css/hospitality_portal.css',
    #     ],
    # },
    'images': [
        'static/description/icon.png',
    ],
    
    'installable': True,
    'auto_install': False,
    'application': True,
    'sequence': 10,
}

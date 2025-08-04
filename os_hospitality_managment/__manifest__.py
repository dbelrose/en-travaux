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

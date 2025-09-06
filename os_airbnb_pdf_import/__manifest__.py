{
    'name': 'Import Réservations Airbnb',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Import des réservations Airbnb depuis PDF',
    'description': """
Import Réservations Airbnb
=========================

Ce module permet d'importer les réservations Airbnb depuis les fichiers PDF 
et de créer automatiquement :

* Les contacts clients avec toutes leurs informations
* Les lignes de réservation avec les détails du séjour
* La gestion des montants et commissions

Fonctionnalités :
-----------------
* Extraction automatique des données depuis les PDF Airbnb
* Création automatique des contacts clients
* Gestion des types d'hébergement
* Calcul automatique des nuitées et taxes
* Support multidevise (EUR vers XPF)

""",
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'depends': [
        'base',
        'sale',
        'product',
        'account',
        'os_hospitality_managment',
    ],
    'external_dependencies': {
        'python': ['PyPDF2'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/airbnb_pdf_importer_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
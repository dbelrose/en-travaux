{
    'name': 'Import Réservations Airbnb PDF',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Import des réservations Airbnb depuis PDF',
    'description': """
Import Réservations Airbnb PDF
==============================

Ce module étend le système d'import de réservations pour supporter 
les fichiers PDF d'Airbnb en complément des fichiers Excel de Booking.com.

Fonctionnalités :
-----------------
* Extraction automatique des données depuis les PDF Airbnb
* Intégration parfaite avec le système de gestion des réservations existant
* Création automatique des contacts clients avec toutes leurs informations
* Support multidevise (EUR vers XPF) avec taux configurable
* Détection automatique des doublons
* Gestion des types d'hébergement
* Calcul automatique des nuitées et taxes de séjour
* Traçabilité de l'origine des réservations (Airbnb vs Booking.com)

Workflow d'import :
------------------
1. Créer ou sélectionner un import existant
2. Utiliser le bouton "Importer PDF Airbnb"
3. Sélectionner le fichier PDF de la réservation
4. Validation et création automatique de la réservation
5. Mise à jour des statistiques et déclarations

Compatibilité :
--------------
* Compatible avec les PDF Airbnb français et anglais
* Fonctionne avec tous les types d'hébergements
* S'intègre aux déclarations trimestrielles existantes

""",
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'depends': [
        'base',
        'os_hospitality_managment',
    ],
    'external_dependencies': {
        'python': ['PyPDF2'],
    },
    'data': [
        'data/res_partner_category_data.xml',
        'security/ir.model.access.csv',
        'views/airbnb_pdf_importer_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,  # Module d'extension, pas application standalone
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 100,
}

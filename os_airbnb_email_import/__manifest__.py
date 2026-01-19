{
    'name': 'Import Réservations Airbnb par Email',
    'version': '17.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Import automatique des réservations Airbnb depuis les emails',
    'description': """
Import Réservations Airbnb par Email
=====================================

Ce module automatise complètement l'import des réservations Airbnb depuis les emails
de notification envoyés par automated@airbnb.com.

Fonctionnalités principales :
------------------------------
* **Connexion IMAP automatique** : Récupération des emails toutes les 15 minutes
* **Parsing intelligent** : Extraction automatique de toutes les données depuis l'email HTML
* **Intégration CRM** : Création automatique de leads avec pipeline de suivi
* **Multi-société** : Support complet pour plusieurs hébergeurs
* **Détection doublons** : Ignore les emails déjà traités (rappels Airbnb)
* **Création automatique** :
  - Contact client avec photo Airbnb
  - Réservation complète avec toutes les données
  - Lead CRM avec historique email
  - Liaison aux vues mensuelles et trimestrielles

Workflow automatique :
----------------------
1. Email reçu → Lead CRM créé (stage "Nouveau")
2. Parsing HTML → Extraction des données
3. Création contact + réservation → Lead passe en "Confirmé"
4. J-0 arrivée → Lead passe en "Arrivé"
5. J+0 départ → Lead passe en "Terminé"

Configuration :
---------------
* Paramétrage IMAP par société (Settings > Companies)
* Taux de change dynamique (1000 XPF = 8.38 EUR)
* Recherche logement via champ "Description vente"
* Journal de traitement des emails

Compatible avec :
-----------------
* os_hospitality_managment (requis)
* os_airbnb_pdf_import (complémentaire)
* crm (intégré)

""",
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'depends': [
        'base',
        'crm',
        'os_hospitality_managment',
    ],
    'external_dependencies': {
        'python': ['email', 'imaplib', 'ssl'],
    },
    'data': [
        # Security
        'security/ir.model.access.csv',
        
        # Data
        'data/crm_stage_data.xml',
        'data/ir_cron_fetch_emails.xml',
        
        # Views
        'views/res_company_views.xml',
        'views/crm_lead_views.xml',
        'views/airbnb_email_log_views.xml',
        'views/booking_import_line_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'sequence': 95,

    # HOOKS pour gérer la migration
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
}

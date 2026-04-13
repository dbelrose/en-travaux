{
    'name': 'OS Auxiliaire Médical',
    'version': '17.0.2.0.0',
    'summary': 'Gestion des feuilles de soins et bordereaux CPS Polynésie française',
    'description': """
Gestion complète des feuilles de soins auxiliaires médicaux pour la
Caisse de Prévoyance Sociale (CPS) de Polynésie française.

Fonctionnalités :
- Saisie des feuilles de soins (FSA25)
- Catalogue d'actes par profession (AMO, AMK, AMI, AMS)
- Modèles de feuilles réutilisables par profession
- Gestion des patients / bénéficiaires (lien res.partner)
- Génération automatique des bordereaux mensuels
- Export Excel et PDF des bordereaux
- Suivi tiers payant (CPS + patient)
""",
    'author': 'OpalSea',
    'website': 'https://www.opalsea.site',
    'category': 'Healthcare',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'partner_firstname',   # OCA — champs firstname / lastname sur res.partner
        'partner_contact_birthdate',   # OCA — champ birthdate_date sur res.partner
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/ir_rule_multi_company.xml',

        'data/ir_sequence_data.xml',
        # Catalogue des actes — chargé avant les vues pour que les données
        # soient disponibles dès l'installation
        'data/cps_acte_type_orthophoniste_data.xml',
        'data/cps_acte_type_orthoptiste_data.xml',
        'data/cps_acte_type_pedicure_data.xml',
        'data/cps_acte_type_infirmier_data.xml',
        'data/cps_acte_type_kinesitherapeute_data.xml',

        'views/praticien_views.xml',
        'views/patient_views.xml',
        'views/acte_type_server_action.xml',
        'views/acte_type_views.xml',
        'views/feuille_modele_views.xml',
        'views/feuille_soins_views.xml',
        'views/bordereau_views.xml',
        'views/menu_views.xml',
        'report/report_bordereau.xml',
        'report/report_feuille_soins.xml',
        'wizards/wizard_bordereau_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'icon': 'static/description/icon.png',
}

{
    'name': 'OS Auxiliaire Médical',
    'version': '17.0.1.0.0',
    'summary': 'Gestion des feuilles de soins et bordereaux CPS Polynésie française',
    'description': """
Gestion complète des feuilles de soins auxiliaires médicaux pour la
Caisse de Prévoyance Sociale (CPS) de Polynésie française.

Fonctionnalités :
- Saisie des feuilles de soins (FSA25)
- Gestion des patients / bénéficiaires
- Génération automatique des bordereaux mensuels
- Export Excel et PDF des bordereaux
- Suivi tiers payant (CPS + patient)
""",
    'author': 'Cabinet COEUR Audrey',
    'category': 'Healthcare',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/praticien_views.xml',
        'views/patient_views.xml',
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

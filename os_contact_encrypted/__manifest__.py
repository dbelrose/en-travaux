{
    'name': 'OS Contact Encrypted',
    'version': '17.0.3.0.0',
    'summary': 'Chiffrement RSA des contacts — architecture satellite, zéro colonne sur res.partner',
    'description': """
        Chiffrement asymétrique RSA des champs d'identification des contacts (res.partner).

        v3 — Architecture satellite (partner.crypto.data) :
        - Zéro colonne ajoutée sur res.partner → aucune migration SQL lors des mises à jour
        - Multi-société natif (company_id sur chaque enregistrement chiffré)
        - Index ciblés sur partner_id et token (performance)
        - Compatible ir.rule pour cloisonnement par société

        Fonctionnalités :
        - Recherche semi-aveugle (ZK) via tokens HMAC-SHA256 sur le nom
        - Choix des champs à chiffrer par utilisateur (préférences)
        - Champs "obligatoires" non désactivables (config admin)
        - Notification d'initialisation discrète (info, non sticky, une fois/session)
        - Wizard d'initialisation des clés RSA
        - Wizard de changement de mot de passe avec re-chiffrement automatique
        - Récupération d'urgence via clé administrateur RSA-4096
        - Journal d'audit des accès d'urgence
    """,
    'category': 'Tools/Security',
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'depends': ['base', 'mail', 'contacts', 'web'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'wizards/init_keypair_wizard_views.xml',
        'wizards/change_password_wizard_views.xml',
        'wizards/emergency_export_wizard_views.xml',
        'views/encrypted_field_config_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/res_users_views_pref.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'os_contact_encrypted/static/src/js/decrypt_widget.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
    'external_dependencies': {
        'python': ['cryptography'],
    },
}

{
    'name': 'OS Contact Encrypted',
    'version': '17.0.4.0.0',
    'summary': 'Chiffrement RSA des contacts — ZK-friendly, recherche multi-mots, aperçu partiel configurable',
    'description': """
        Chiffrement asymétrique RSA des champs d'identification des contacts (res.partner).

        v4 — Recherche ZK améliorée + UX :
        - Recherche multi-mots : intersection de tokens HMAC (ex. "Dupo J" trouve "Dupont Jean")
        - Longueur minimale de préfixe configurable dans Paramètres généraux
        - Aperçu du nom configurable : N premiers caractères + initiales (ex. "Dupo. J.")
        - Champs d'affichage éditables (inverse functions) : pas de double saisie
        - phone_display et mobile_display correctement affichés en vue liste
        - Menu Récupération d'urgence accessible depuis le menu principal
        - Architecture satellite inchangée (zéro colonne sur res.partner)
    """,
    'category': 'Tools/Security',
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'depends': ['base', 'mail', 'contacts', 'web', 'base_setup'],
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
        'views/res_config_settings_views.xml',
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

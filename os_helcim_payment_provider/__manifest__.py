# -*- coding: utf-8 -*-
{
    'name': 'Payment Provider: Helcim',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': "Intégration du fournisseur de paiement Helcim via HelcimPay.js",
    'description': """
        Module d'intégration Helcim pour Odoo 17.
        Utilise l'API HelcimPay.js pour un traitement sécurisé des paiements
        par carte de crédit/débit sans que les données sensibles ne transitent
        par les serveurs Odoo.

        Fonctionnalités :
        - Paiement en ligne via modal HelcimPay.js (PCI-DSS compliant)
        - Support multi-devises (XPF/CFP pour la Polynésie française)
        - Mode test et production
        - Remboursements (refund / reverse)
        - Validation HMAC SHA-256 des réponses
    """,
    'author': 'Opensense',
    'website': 'https://www.opensense.pf',
    'license': 'LGPL-3',
    'depends': ['payment'],
    'data': [
        # Aucun fichier data/ : le provider, la méthode de paiement et les vues
        # sont tous créés via post_init_hook (ORM) après chargement complet
        # des modèles Python et création des colonnes SQL helcim_*.
        'views/payment_helcim_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'os_helcim_payment_provider/static/src/js/payment_form.js',
        ],
    },
    'images': ['static/src/img/helcim_logo.svg'],
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}

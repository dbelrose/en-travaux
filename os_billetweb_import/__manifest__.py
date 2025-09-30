{
    "name": "BilletWeb Import",
    "version": "17.0.1.0.0",
    "summary": "Import des virements BilletWeb et génération automatique des paiements et factures.",
    "author": "OpalSea",
    "category": "Accounting",
    'website': 'https://www.opalsea.site',
    "depends": [
        "os_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/billetweb_import_views.xml",
        "wizard/billetweb_import_action.xml",
        "data/mail_template_billetweb.xml",
        "views/action_views.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}

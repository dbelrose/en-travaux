# -*- coding: utf-8 -*-
{
    'name': 'Import Factures Fournisseurs par Email',
    'version': '17.0.1.0.0',
    'summary': 'Importe automatiquement les factures fournisseurs depuis des emails (.eml) '
               'et alimente la comptabilité analytique par produit/logement.',
    'description': """
Supplier Bill Email Import
==========================
Ce module permet de :

* Définir des règles de parsing par fournisseur (EDT, Téléphonie, Syndic…)
* Importer des fichiers .eml via un assistant
* Extraire automatiquement : n° facture, date, montant, n° contrat
* Retrouver le produit/logement via l'attribut produit "N° de contrat EDT"
* Créer la facture fournisseur avec distribution analytique par logement

Fournisseurs supportés (configurables) :
- EDT / Engie (électricité Polynésie)
- Extensible à tout fournisseur via les règles de parsing
    """,
    'author': 'Custom',
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
        'analytic',
        'product',
        'mail',       # mail.thread, mail.alias.mixin, routing des emails entrants
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/supplier_email_rule_data.xml',
        'views/supplier_email_rule_views.xml',
        'views/import_eml_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

# -*- coding: utf-8 -*-
{
    'name': 'Import Factures & Alertes Bancaires par Email',
    'version': '17.0.3.0.0',
    'summary': 'Importe automatiquement les factures fournisseurs et les alertes '
               'bancaires depuis des emails (.eml), avec rapprochement automatique.',
    'description': """
Supplier Bill & Bank Alert Email Import — v3
============================================
Ce module permet de :

* Définir des règles de parsing fournisseurs (EDT, Téléphonie, Syndic…)
* Définir des règles de parsing d'alertes bancaires (Marara Paiement, OPT…)
* Importer des fichiers .eml via un assistant ou automatiquement via fetchmail

Factures fournisseurs :
  * Extraction automatique : n° facture, date, montant, n° contrat
  * Exploitation de la pièce jointe PDF (pdfminer.six, pypdf, PyPDF2)
  * Extraction des lignes de détail du PDF
  * Validation automatique + paiement sortant + rapprochement

Alertes bancaires (nouveauté v3) :
  * Extraction de chaque opération (date, sens, montant, libellé)
  * Création de account.bank.statement.line dans le journal bancaire
  * Rapprochement automatique contre les pièces ouvertes (montant exact)
  * Déduplication : un email traité deux fois ne crée pas de doublon

Dépendance optionnelle :
  pip install pdfminer.six
    """,
    'author': 'OpalSea',
    'maintainer': ['OpalSea'],
    'category': 'Accounting/Accounting',
    'depends': [
        'account',
        'analytic',
        'product',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/supplier_email_rule_data.xml',
        'views/supplier_email_rule_views.xml',
        'views/bank_alert_rule_views.xml',
        'views/import_eml_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

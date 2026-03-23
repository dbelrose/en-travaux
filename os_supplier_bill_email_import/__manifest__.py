# -*- coding: utf-8 -*-
{
    'name': 'Import Factures & Alertes Bancaires par Email',
    'version': '17.0.3.2.0',
    'summary': 'Importe automatiquement les factures fournisseurs et les alertes '
               'bancaires depuis des emails (.eml), avec rapprochement automatique.',
    'description': """
Supplier Bill & Bank Alert Email Import — v3.2
==============================================
Ce module permet de :

* Définir des règles de parsing fournisseurs (EDT, Téléphonie, Syndic…)
* Définir des règles de parsing d'alertes bancaires (Marara Paiement, OPT…)
* Importer des fichiers .eml via un assistant ou automatiquement via fetchmail

Factures fournisseurs :
  * Extraction automatique : n° facture, date, montant, n° contrat
  * Exploitation de la pièce jointe PDF (pdfminer.six, pypdf, PyPDF2)
  * Extraction des lignes de détail du PDF
  * Validation automatique + paiement sortant + rapprochement

Alertes bancaires :
  * Extraction de chaque opération (date, sens, montant, libellé)
  * Création de account.bank.statement.line dans le journal bancaire
  * Rapprochement automatique contre les pièces ouvertes (montant exact)
  * Déduplication : un email traité deux fois ne crée pas de doublon

Nouveautés v3.1 :
  * Attributs produit et tantième sélectionnés via un champ Many2one
    (product.attribute) plutôt que saisis librement — plus robuste et
    insensible aux fautes de frappe ou renommages.

Nouveautés v3.2 :
  * Extraction du XML Factur-X via le module Python factur-x
    (pip install factur-x) — prioritaire sur le fallback pypdf.
    Gère nativement tous les profils EN 16931, ZUGFeRD 2.x,
    Factur-X et XRechnung sans liste de noms de fichiers figée.
    Fallback transparent vers pypdf si factur-x n'est pas installé.

Dépendances optionnelles (pip) :
  pip install pdfminer.six   # extraction texte PDF (recommandé)
  pip install factur-x       # extraction XML Factur-X (recommandé)
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

# -*- coding: utf-8 -*-
{
    'name': 'Import Factures Fournisseurs par Email',
    'version': '17.0.2.0.0',
    'summary': 'Importe automatiquement les factures fournisseurs depuis des emails (.eml), '
               'exploite les pièces jointes PDF, enregistre et rapproche les paiements.',
    'description': """
Supplier Bill Email Import — v2
================================
Ce module permet de :

* Définir des règles de parsing par fournisseur (EDT, Téléphonie, Syndic…)
* Importer des fichiers .eml via un assistant ou automatiquement via fetchmail
* Extraire automatiquement : n° facture, date, montant, n° contrat

Nouveautés v2 :
* Exploiter la pièce jointe PDF de l'email (pdfminer.six, pypdf, PyPDF2)
* Préférer le PDF au corps de l'email ou combiner les deux
* Extraire les lignes de détail du PDF (une ligne de facture par ligne PDF)
* Valider automatiquement la facture après création
* Enregistrer un paiement sortant et le rapprocher de la facture

Dépendance optionnelle :
  pip install pdfminer.six
    """,
    'author': 'Custom',
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
        'views/import_eml_wizard_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

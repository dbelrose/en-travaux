# -*- coding: utf-8 -*-
{
    "name": "PF: GOV: RCH",
    "version": "1.0",
    "category": "French Polynesian localization",
    "description": """
        This is the module to manage imports for RCH department of French Polynesia
    """,
    "author": "Didier BELROSE",
    "company": "Polynésie française",
    "depends": [
        "rch_profile",
    ],
    'external_dependencies': {
        'python': ['bs4', 'pandas'],  # ou 'beautifulsoup4'
    },
    "data": [
        "data/ir_attachment_category_data.xml",

        "security/ir.model.access.csv",
        "security/ir_module_category_data.xml",
        "security/res_groups_data.xml",
        "security/security.xml",

        "views/account_bank_statement_views.xml",
        "views/bank_statement_import_views_atea.xml",
        "views/bank_statement_import_views_ccp.xml",
        "views/bank_statement_import_views_ieom.xml",
        "views/bank_statement_import_views_paierie.xml",
        "views/bank_statement_import_views_paierie_dif.xml",
        "views/bank_statement_import_views_quittancier.xml",
        "views/account_journal.xml",
    ],
    "images": [
        "static/description/icon.png",
    ],
    "license": "AGPL-3",
    "installable": True,
    "application": True,
}

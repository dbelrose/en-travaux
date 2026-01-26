{
    'name': 'JOPF PDF Import',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'Import associations et membres depuis PDF JOPF',
    'description': """
        Import automatique depuis le Journal Officiel de Polynésie Française
        ====================================================================

        ✓ OCR de PDF scannés
        ✓ Parsing intelligent
        ✓ Gestion des doublons
        ✓ Traçabilité complète
        ✓ Logs détaillés
    """,
    'author': 'Votre Société',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts'],
    'external_dependencies': {
        'python': ['pdf2image', 'pytesseract', 'Pillow'],
    },
    'data': [
        'security/jopf_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/partner_categories.xml',
        'views/jopf_import_views.xml',
        'views/res_partner_views.xml',
        'views/jopf_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

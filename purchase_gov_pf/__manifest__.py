# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
# https://www.tauturu.gov.pf/front/ticket.form.php?id=137339
{
    'name': "Purchase GOV PF",

    'summary': 'PF GOV Customization',
    'description': """
This module is for customization of GOV PF in French Polynesia.
Features :
    """,
    'author': 'Cyril VINH-TUNG (INVITU)',
    'maintainer': 'Didier BELROSE (DSI)',
    'website': '',
    'category': 'Custom',
    'version': '1.0',
    'depends': [
        'base',
        'purchase_stock',
        'purchase_requisition',
        'l10n_pf_public_purchase_ui_rename',
        'l10n_pf_purchase_freight',
        'hr_expense_gov_pf',
    ],
    'data': [
        'security/purchase_gov_pf_security.xml',

        'data/analytic_account_data.xml',
        'data/purchase_order_type.xml',
        'data/purchase_requisition_data.xml',

        'report/purchase_reports.xml',
        'report/purchase_order_templates.xml',
        'report/purchase_requisition_templates.xml',

        'views/account_move_views.xml',
        'views/purchase_requisition_views.xml',
        'views/purchase_views.xml',
        'views/res_company_views.xml',
        'views/res_partner_views.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'license': 'AGPL-3',
}

{
    'name': 'Purchase Module Customization',
    'version': '14.0.1.0.0',
    'author': 'Didier BELROSE (DSI)',
    'website': 'https://www.tauturu.gov.pf/front/ticket.form.php?id=137339',
    'category': 'Purchases',
    'summary': 'Copy analytic tags from the first line to all other lines',
    'depends': [
        'purchase',
        'purchase_requisition',
        'purchase_gov_pf',
    ],
    'data': [
        'views/purchase_order_views.xml',
        'views/purchase_requisition_views.xml',
    ],
}
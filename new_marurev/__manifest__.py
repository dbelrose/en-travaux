# -*- coding: utf-8 -*-
{
    'name': 'Manureva',
    'version': '1.2',
    'category': 'Tools',
    'description': u"""
Facturation des redevances aéoportuaires
""",
    'author': 'Didier Belrose',
	'maintainer': 'Didier BELROSE (DSI)',
	"website": "https://gitlab.gov.pf/odoo/addons/-/tree/master/sources/manureva",
	'company': 'Polynésie française',
    'depends': [
		'l10n_pf_gov_dac',
		'multi_step_wizard',
    ],
    'data': [
		'views/manureva_view.xml',
		'views/aerodrome.xml',
		'views/balisage.xml',
		'views/constructeur.xml',
		'views/type_aeronef.xml',
		'views/type_aerodrome.xml',
		'views/type_activite.xml',
		'views/aeronef.xml',
		'views/facture.xml',
		'views/ligne_facture.xml',
		'views/nc_depot.xml',
		'views/periode.xml',
		'views/param_att.xml',
		'views/param_pax.xml',
		'views/seac.xml',
		'views/tva.xml',
		'views/type_taxe.xml',
		'views/usager.xml',
		'views/vol_public_aerodrome.xml',

		'views/facture_globale.xml',

		'wizard/periode_wizard.xml',
		'wizard/vol_public_aerodrome_wizard.xml',
		'wizard/periode_imprimer_facture_wizard.xml',
		'wizard/periode_supprimer_facture_wizard.xml',

		'security/asset_security.xml',
		'security/ir.model.access.csv',
	],
	'images': [
		'static/logo.png',
	],
	'license': 'AGPL-3',
	'installable': True,
	'auto_install': False,
	'application': True,
}

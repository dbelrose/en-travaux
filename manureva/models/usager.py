# -*- coding: utf-8 -*-
from odoo import models, fields

# Table des transporteurs aériens
class Usager(models.Model):
	_description = 'Usagers'
	_inherits = {'res.partner': 'partner_id'}
	_name = 'manureva.usager'
	_order = 'partner_id'
	_rec_name = 'cie_oaci'

	aeronef_ids = fields.One2many(
		'manureva.aeronef',
		'usager_id',
		string='Aéronefs',
	)
	facture_ids = fields.One2many(
		'manureva.facture',
		'usager_id',
		string='Factures',
	)
	cie_oaci = fields.Char(
		string='Code du transporteur',
	)
	cie_pays = fields.Many2one(
		'res.country',
		string='Pays du transporteur',
	)
	name = fields.Char(
		related='partner_id.name',
		store=True,
	)
	partner_id = fields.Many2one(
		'res.partner',
		required=True,
		ondelete='restrict',
		auto_join=True,
		string='Contact',
		help="Informations de contact relatives à l'usager",
	)
	type_activite_id = fields.Many2one('manureva.type_activite', string='Type d’activité')
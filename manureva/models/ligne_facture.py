# -*- coding: utf-8 -*-
from . import type_aeronef
from odoo import models, fields, api

# Lignes de facture
class LigneFacture(models.Model):
	_name = 'manureva.ligne_facture'
	_description = 'Lignes de facture'

	name = fields.Char(
		string='Ligne',
		compute='_compute_name',
		store=True,
		group_operator='count',
	)
	facture_id = fields.Many2one(
		'manureva.facture',
		ondelete='cascade',
	)
	type_aeronef_id = fields.Many2one(
		'manureva.type_aeronef',
		string='Type'
	)
	atterrissage = fields.Float(
		string='Atterrissage'
	)
	passager = fields.Float(
		string='Passagers'
	)
	balisage = fields.Float(
		string='Balisage'
	)
	stationnement = fields.Float(
		string='Stationnement'
	)

	_sql_constraints = [
		('unique_ligne_facture', 'unique(facture_id, type_aeronef_id)', "Cette ligne de facture existe déjà!"),
	]

	@api.depends('type_aeronef_id.name')
	def _compute_name(self):
		for record in self:
			record.name = record.type_aeronef_id.name
# -*- coding: utf-8 -*-
from . import type_taxe
from odoo import models, fields, api
from datetime import date, datetime

class TVA(models.Model):
	_name = 'manureva.tva'
	_description = 'TVA'
	active = fields.Boolean(string='Actif', compute='_compute_active', store=True)
	name = fields.Char(string='TVA', related='type_taxe_id.name')
	debut = fields.Date(string='Début de validité')
	fin = fields.Date(string='Fin de validité')
	taux = fields.Float(string='Taux')
	type_taxe_id = fields.Many2one('manureva.type_taxe', string='Type de taxe', required=True)
	_sql_constraints = [
        ('unique_tva', 'unique(debut, fin, type_taxe_id)', "Cette TVA existe déjà!"),
        ('fin_superieure_a_debut', 'check(fin>=debut)', "La date de fin doit être supérieure à la date de début!"),
    ]
	@api.depends('debut','fin')
	def _compute_active(self):
		for record in self:
			record.active = record.debut <= date.today() <= record.fin
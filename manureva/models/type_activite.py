# -*- coding: utf-8 -*-

from odoo import models, fields

class TypeActivite(models.Model):
	_name = 'manureva.type_activite'
	_description = 'Types d’activité'

	name = fields.Char(
		string='Type d’activité',
		required=True,
	)
	usager_ids = fields.One2many(
		'manureva.usager',
		'type_activite_id',
		string='Opérateurs',
	)
	# partner_ids = fields.One2many('res.partner', 'type_activite_id', string='Compagnies')
	_sql_constraints = [
        ('unique_type_activite', 'unique(name)', "Ce type d'activité existe déjà!"),
    ]
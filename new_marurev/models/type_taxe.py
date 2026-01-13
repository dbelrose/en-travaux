# -*- coding: utf-8 -*-

from odoo import models, fields

class TypeTaxe(models.Model):
	_name = 'manureva.type_taxe'
	_description = 'Types de taxe'
	name = fields.Char(string='Type de taxe', required=True)
	_sql_constraints = [
        ('unique_type_taxe', 'unique(name)', "Ce type de taxe existe déjà!"),
    ]
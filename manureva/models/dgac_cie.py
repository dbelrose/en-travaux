# -*- coding: utf-8 -*-
from odoo import models, fields

# Table des transporteurs aériens			
class DGAC_CIE(models.Model):
	_name = 'manureva.dgac_cie'
	_description = 'Transporteurs aériens'
	name = fields.Char(string='Nom', related='cie_nom', store=True)
	cie_oaci = fields.Char(string='Code du transporteur', store=True)
	cie_pays = fields.Many2one('res.country', string='Pays du transporteur', store=True)
	cie_nom = fields.Char(string='Libellé du transporteur', store=True)
	type_activite_id = fields.Many2one('manureva.type_activite', string='Type d’activité', store=True)
	_sql_constraints = [
		('unique_cie_oaci', 'unique(cie_oaci)', "Ce code transporteur existe déjà!"),
	]
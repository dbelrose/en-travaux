# -*- coding: utf-8 -*-

from odoo import models, fields

# Table des codes IATA des causes de retard			
class ManurevaDGAC_RTD(models.Model):
	_name = 'manureva.dgac_rtd'
	_description = 'Codes IATA des causes de retard'
	name = fields.Char(string='Nom', related='rtd_nom', store=True)
	rtd_cat = fields.Char(string='Classe de retard')
	rtd_alpha = fields.Char(string='Code cause de retard en lettres')
	rtd_num = fields.Integer(string='Code cause de retard en chiffres')
	rtd_nom = fields.Char(string='Libellé en anglais')
	_sql_constraints = [
		('unique_rtd_alpha', 'unique(rtd_alpha)', "Ce code cause de retard en lettres existe déjà!"),
		('unique_rtd_num', 'unique(rtd_num)', "Ce code cause de retard en chiffres existe déjà!"),
	]
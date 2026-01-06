# -*- coding: utf-8 -*-

from odoo import models, fields

class ManurevaFacture(models.Model):
	_name = 'manureva.facture'
	_description = 'Factures'
	name = fields.Char(string='Référence')
	facture = fields.Integer(string='Numéro')
	aerodrome_id = fields.Many2one('manureva.aerodrome', string='Aérodrome')
	usager_id = fields.Many2one('manureva.usager', string='Opérateur')
	periode_id = fields.Many2one('manureva.periode', string='Période')
	ligne_facture_ids = fields.One2many('manureva.ligne_facture', 'facture_id', string='Lignes de facture')
	_sql_constraints = [
        ('unique_facture', 'unique(periode_id, usager_id, aerodrome_id)', "Cette facture existe déjà!"),
    ]

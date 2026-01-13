# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date, datetime


# Redevance passager
class ParamPax(models.Model):
    _name = 'manureva.param_pax'
    _description = 'Redevance passager'
    active = fields.Boolean(string='Actif', compute='_compute_active', store=True)
    name = fields.Char(string='Passager')
    debut = fields.Date(string='Début de validité')
    montant = fields.Float(string='Montant')
    fin = fields.Date(string='Fin de validité')
    type_aerodrome_id = fields.Many2one('manureva.type_aerodrome', string='Type d’aérodrome', required=True)
    _sql_constraints = [
        ('unique_param_pax', 'unique(debut, fin, type_aerodrome_id)', "Cette règle existe déjà!"),
    ]

    @api.depends('debut', 'fin')
    def _compute_active(self):
        for record in self:
            record.active = record.debut <= date.today() <= record.fin

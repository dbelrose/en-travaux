# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date, datetime


# Redevance atterrissage
class ParamAtt(models.Model):
    _name = 'manureva.param_att'
    _description = 'Redevance atterrissage'
    active = fields.Boolean(string='Actif', compute='_compute_active', store=True)
    name = fields.Char(string='Atterrissage')
    avec_correction = fields.Boolean(string='Avec correction')
    domestique = fields.Boolean(string='Domestique')
    debut = fields.Date(string='Début de validité')
    base = fields.Float(string='Base')
    coefficient = fields.Float(string='Coefficient')
    correction = fields.Float(string='Correction')
    fin = fields.Date(string='Fin de validité')
    mmd_inf = fields.Float(string='MMD inf')
    mmd_sup = fields.Float(string='MMD sup')
    type_aerodrome_id = fields.Many2one('manureva.type_aerodrome', string='Type d’aérodrome', required=True)
    _sql_constraints = [
        ('unique_param_att', 'unique(debut, fin, mmd_inf, mmd_sup, type_aerodrome_id)', "Cette règle existe déjà!"),
    ]

    @api.depends('debut', 'fin')
    def _compute_active(self):
        for record in self:
            record.active = record.debut <= date.today() <= record.fin

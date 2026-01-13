# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date


class ManurevaBalisage(models.Model):
    _name = 'manureva.balisage'
    _description = 'Paramètres pour le calcul de la redevance balisage'
    active = fields.Boolean(string='Actif', compute='_compute_active', store=True)
    name = fields.Char(string='Balisage')
    debut = fields.Date(string='Début de validité')
    fin = fields.Date(string='Fin de validité')
    avant = fields.Float(string='Avant')
    apres = fields.Float(string='Après')
    montant = fields.Float(string='Montant')
    type_aerodrome_id = fields.Many2one('manureva.type_aerodrome', string='Type d’aérodrome', required=True)
    _sql_constraints = [
        ('unique_balisage', 'unique(debut, fin, type_aerodrome_id)', "Cette règle existe déjà!"),
    ]

    @api.depends('debut', 'fin')
    def _compute_active(self):
        for record in self:
            record.active = record.debut <= date.today() <= record.fin

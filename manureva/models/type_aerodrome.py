# -*- coding: utf-8 -*-

from odoo import models, fields


class TypeAerodrome(models.Model):
    _name = 'manureva.type_aerodrome'
    _description = 'Types d’aérodrome'

    name = fields.Char(
        string='Type d’aérodrome',
        required=True,
    )
    a_facturer = fields.Boolean(
        string='A facturer',
    )
    aerodrome_ids = fields.One2many(
        'manureva.aerodrome',
        'type_aerodrome_id',
        string='Aérodromes',
    )

    _sql_constraints = [
        ('unique_type_aerodrome', 'unique(name)', "Ce type d’aérodrome existe déjà!"),
    ]

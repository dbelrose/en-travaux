# -*- coding: utf-8 -*-

from odoo import models, fields


class Facture(models.Model):
    _name = 'manureva.facture'
    _description = 'Factures'
    # _order = 'facture'

    name = fields.Char(
        string='Référence',
    )
    facture = fields.Integer(
        string='Numéro',
        group_operator='count',
    )
    aerodrome_id = fields.Many2one(
        'manureva.aerodrome',
        string='Aérodrome',
        group_operator='count_distinct',
        required=True,
    )
    usager_id = fields.Many2one(
        'manureva.usager',
        string='Opérateur',
        group_operator='count_distinct',
        required=True,
    )
    periode_id = fields.Many2one(
        'manureva.periode',
        string='Période',
        group_operator='count_distinct',
        required=True,
    )
    ligne_facture_ids = fields.One2many(
        'manureva.ligne_facture',
        'facture_id',
        string='Lignes de facture',
    )

    _sql_constraints = [
        ('unique_facture', 'unique(periode_id, usager_id, aerodrome_id)', "Cette facture existe déjà!"),
    ]

# -*- coding: utf-8 -*-

from odoo import models, fields, api


# Modèles d’aéronef
class TypeAeronef(models.Model):
    _name = 'manureva.type_aeronef'
    _description = 'Modèles d’aéronef'
    # _parent_store = True

    aeronef_ids = fields.One2many(
        'manureva.aeronef',
        'type_aeronef_id',
        string='Aéronefs',
    )
    name = fields.Char(
        string="Type d'aéronef",
        default='_default_name',
    )
    constructeur_id = fields.Many2one(
        comodel_name='manureva.constructeur',
        string='Constructeur',
        # required=True,
        # store=True,
    )
    # parent_path = fields.Char(
    #     index=True,
    # )
    pax = fields.Integer(
        string='Nombre de sièges passager',
    )
    tonnage = fields.Float(
        string='Tonnage',
    )
    typ_gnp = fields.Char(
        string="Type de motorisation",
    )
    typ_nom = fields.Char(
        string="Libellé OACI",
    )
    typ_oaci = fields.Char(
        string="Code OACI",
        required=True,
    )

    _sql_constraints = [
        ('unique_type_aerodnef', 'unique(name)', "Ce type d’aéronef existe déjà!"),
    ]

    @api.onchange('typ_oaci')
    def _onchange_oaci(self):
        if self.typ_oaci != None:
            self.name = self.typ_oaci

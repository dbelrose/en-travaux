# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Aeronef(models.Model):
    _name = 'manureva.aeronef'
    _description = 'Aéronefs'
    _order = 'usager_id, constructeur_id, typ_oaci, name'

    usager_id = fields.Many2one(
        'manureva.usager',
        string='Opérateur',
        required=True,
    )
    name = fields.Char(
        string='Aéronef',
        required=True,
    )
    constructeur_id = fields.Many2one(
        comodel_name='manureva.constructeur',
        string='Constructeur',
        related='type_aeronef_id.constructeur_id',
    )
    type_aeronef_id = fields.Many2one(
        'manureva.type_aeronef',
        string='Type d’aéronef',
        required=True,
    )
    typ_oaci = fields.Char(
        string="Code OACI",
        related='type_aeronef_id.typ_oaci',
    )
    tonnage = fields.Float(
        string='Tonnage',
        related='type_aeronef_id.tonnage'
    )
    pax = fields.Integer(
        string='Nombre de sièges passager',
        default=lambda self: self.env['manureva.type_aeronef'].search([('id', '=', self.type_aeronef_id.id)]).pax
    )

    _sql_constraints = [
        ('unique_aeronef', 'unique(name)', "Cet aéronef existe déjà!"),
    ]

    @api.onchange('type_aeronef_id')
    def _onchange_type_aeronef_id(self):
        if self.type_aeronef_id:
            self.pax = self.type_aeronef_id.pax

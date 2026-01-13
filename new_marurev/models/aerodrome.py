# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Aerodrome(models.Model):
    _name = 'manureva.aerodrome'
    _description = 'Aérodromes'

    apt_oaci = fields.Char(
        string='Code OACI',
    )
    apt_nom = fields.Char(
        string='Libellé',
    )
    apt_pays = fields.Many2one(
        'res.country',
        string='Pays (OACI)',
    )
    name = fields.Char(
        string='OACI',
        default='_default_name',
    )
    type_aerodrome_id = fields.Many2one(
        'manureva.type_aerodrome',
        string='Type',
    )
    aerodrome = fields.Char(
        string='Nom',
        default='_default_aerodrome',
    )
    country_id = fields.Many2one(
        'res.country',
        string='Pays',
        dafault='_default_country_id',
    )
    email_ad_pro = fields.Boolean(
        default=False,
        help="L'aérodrome dispose d'une adresse email professionnelle",
        string="Adresse email pro ad",
    )
    email_perso = fields.Char(
        string="Email perso",
    )
    email_pro = fields.Char(
        string="Email pro",
        compute='_compute_email_pro',
    )
    afis = fields.Selection(
        [['Afis', 'Afis'],
         ['-', 'Non'],
         ['ctrl', 'ctrl']],
        string="Afis",
    )
    balisage = fields.Boolean(
        string="Balisage",
    )
    iata = fields.Char(
        string="IATA",
    )
    red_balisage = fields.Integer(
        help="Tarif forfaitaire de la redevance balisage",
        string="Redevance balisage",
        compute='_compute_red_balisage',
    )

    _sql_constraints = [
        ('unique_aerodrome', 'unique(name)', "Cet aérodrome existe déjà!"),
    ]

    def _default_aerodrome(self):
        for record in self:
            if record.apt_nom is not None:
                record.aerodrome = record.apt_nom

    def _default_country_id(self):
        for record in self:
            if record.apt_pays is not None:
                record.country_id = record.apt_pays
            else:
                record.country_id = self.env['res.country'].search([('name', 'ilike', 'polynésie française')],
                                                                   limit=1).id

    def _default_name(self):
        for record in self:
            if record.apt_oaci is not None:
                record.name = record.apt_oaci

    def _compute_email_pro(self):
        for record in self:
            record.email_pro = ''
            if record.email_ad_pro:
                record.email_pro = record.aerodrome.lower().replace(" ","") + '.aerodrome@mail.pf'

    def _compute_red_balisage(self):
        for record in self:
            record.red_balisage = 0
            if record.balisage:
                record.red_balisage = record.env['manureva.balisage'].search([('active',
                                                                               '=',
                                                                               True),
                                                                              ('type_aerodrome_id',
                                                                               '=',
                                                                               record.type_aerodrome_id.id)]
                                                                             ).montant

# -*- coding: utf-8 -*-
from datetime import date, datetime
from odoo import models, fields, api, _


# Fichier des mouvements
class SEAC(models.Model):
    _name = 'manureva.seac'
    _description = 'Fichier des mouvements'

    name = fields.Char(
        string='Nom',
    )
    heure = fields.Datetime(
        string='Heure',
    )
    heure_decimale = fields.Float(
        string='Heure décimale',
        compute='_compute_heure_decimale',
    )
    aerodrome_id = fields.Many2one(
        'manureva.aerodrome',
        string='FC02',
        help="Aérodrome source",
    )
    usager_id = fields.Many2one(
        'manureva.usager',
        string='FC03',
        group_operator='count',
        help="Code du transporteur exploitant",
    )
    vol = fields.Char(
        string='FC13',
        group_operator='count',
        help="Numéro de vol",
    )
    circonstance = fields.Selection(
        [['D', 'Dérouté'], ['N', 'Non dérouté'], ['I', 'Interrompu']],
        default='N',
        string='FC14',
        help="Circonstance du vol",
    )
    mouvement = fields.Selection(
        [['A', 'Arrivée'], ['D', 'Départ']],
        group_operator="count",
        string='FC15',
        help="Mouvement  départ/arrivée",
    )
    aerod_prov_dest = fields.Many2one(
        'manureva.aerodrome',
        string='FC16',
        help="Aérodrome de provenance/destination",
    )
    pax_plus = fields.Integer(
        string='FC18',
        help="Passagers totaux sur l’étape de vol",
    )
    pax_2ans = fields.Integer(
        string='FC19',
        help="Passagers de moins de deux ans sur l’étape de vol",
    )
    pax_moins = fields.Integer(
        string='FC20',
        help="Passagers en transit sur l’étape de vol",
    )
    aeronef_id = fields.Many2one(
        'manureva.aeronef',
        string='FC27',
        group_operator='count_distinct',
        help="Immatriculation de l'aéronef",
    )
    date = fields.Date(
        string='FC32',
        required=True,
        help="Date bloc réelle",
    )
    annee = fields.Integer(
        string="Année",
        compute="_compute_annee",
        readonly=True,
        store=True,
    )
    heure_texte = fields.Char(
        string='FC33',
        required=True,
        help="Heure bloc réelle (HH:MM)",
    )
    date_piste_reelle = fields.Date(
        string='FC34',
        help="Date piste réelle",
    )
    heure_piste_relle = fields.Char(
        string='FC35',
        help="Heure piste réelle (HH:MM)",
    )
    piste_utilisee = fields.Char(
        string='FC42',
        help="Piste utilisée",
    )
    balisage = fields.Selection(
        [('N', 'balisage non en service'), ('S', 'balisage en service')],
        default='N',
        string='FC43',
        help="Balisage en service",
    )
    # Modification du 21/07/2022 : Ajout des ECx_9
    paxlnp1 = fields.Integer(
        string='EC1_9',
        help="Passagers locaux non-payants à l'escale 1",
    )
    paxlnp2 = fields.Integer(
        string='EC2_9',
        help="Passagers locaux non-payants à l'escale 2",
    )
    paxlnp3 = fields.Integer(
        string='EC3_9',
        help="Passagers locaux non-payants à l'escale 3",
    )
    paxlnp4 = fields.Integer(
        string='EC4_9',
        help="Passagers locaux non-payants à l'escale 4",
    )
    paxlnp5 = fields.Integer(
        string='EC5_9',
        help="Passagers locaux non-payants à l'escale 5",
    )

    _sql_constraints = [
        ('unique_mouvement', 'unique(aeronef_id, date, heure_texte, mouvement)', "Ce mouvement existe déjà!"),
    ]

    # Ajout automatique des nouvelles périodes

    @api.model
    def create(self, vals):
        date_mouvement = fields.Date.from_string(vals.get('date'))
        annee = date_mouvement.year
        mois = date_mouvement.month

        usager_id = vals.get('usager_id')

        if self.env['manureva.periode'].search_count([('annee', '=', annee),
                                                ('mois', '=', mois),
                                                ('usager_id', '=', usager_id)]) == 0:
            self.env['manureva.periode'].create({'annee': annee, 'mois': mois, 'usager_id': usager_id,
                                                 'active': True, 'a_facturer': True, 'facture': False})
        return super(SEAC, self).create(vals)

    @api.depends('date')
    def _compute_annee(self):
        for mouvement in self:
            mouvement.annee = mouvement.date.strftime('%Y')

    @api.depends('heure_texte')
    def _compute_heure_decimale(self):
        for mouvement in self:
            mouvement.heure_decimale = float(mouvement.heure_texte[0:4].replace(':', '.'))

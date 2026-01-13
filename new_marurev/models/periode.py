# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date, datetime
from calendar import monthrange
from math import *


# Périodes
class Periode(models.Model):
    _name = 'manureva.periode'
    _description = 'Périodes'
    _order = 'annee desc, mois desc, usager_id'

    active = fields.Boolean(
        string='Actif',
        default=True,
    )
    # a_recuperer = fields.Boolean(
    # 	string='A récupérer',
    # 	help="Les mouvements doivent être récupérés à nouveau.",
    # )
    name = fields.Char(
        string='Période',
        compute='_compute_name',
        store=True,
    )
    usager_id = fields.Many2one(
        'manureva.usager',
        string='Opérateur',
        required=True,
    )
    mois = fields.Integer(
        string='Mois',
        group_operator='count',
    )
    annee = fields.Integer(
        string='Année',
        group_operator='count_distinct',
    )
    a_facturer = fields.Boolean(
        string='A facturer',
        group_operator='bool_or',
    )
    date_debut = fields.Date(
        compute="_compute_date_debut",
        string="Début",
        readonly=True,
        store=True,
    )
    facture = fields.Boolean(
        string='Facturé',
        group_operator='bool_and',
    )
    facture_ids = fields.One2many('manureva.facture', 'periode_id', string='Factures')
    state = fields.Selection([
            ('1a_facturer', 'A facturer'),
            ('2facture', 'Facturé')
            # ('2facture', 'Facturé'),
            # ('3la_imprime', 'Lettre imprimée'),
            # ('4fg_imprime', 'Facture glogale imprimée'),
            # ('5imprime', 'Imprimé en totalité')
        ], string='Etat', compute='_compute_state', store=True, readonly=True)

    _sql_constraints = [
        ('unique_periode', 'unique(annee, mois, usager_id)', "Cette période existe déjà!"),
    ]

    @api.depends('mois', 'annee')
    def _compute_date_debut(self):
        for record in self:
            if 1 <= record.mois <= 12 and 2000 <= record.annee <= 2100:
                d = datetime(record.annee, record.mois, 1)
                record.date_debut = d.date()

    @api.depends('mois', 'annee')
    def _compute_name(self):
        for record in self:
            if 1 <= record.mois <= 12 and 2000 <= record.annee <= 2100:
                record.name = date(record.annee, record.mois, 1).strftime("%B %Y").title() + " " + record.usager_id.cie_oaci

    def imprimer_la_periode(self):
        self.ensure_one()
        url = 'https://<login>:<mot_de_passe>@www.jasper.gov.pf/jasperserver/rest_v2/reports/Aviation_civile/Lettre_d_accompagnement.pdf'\
              + '?annee=' + str(self.annee) \
              + '&p_mois=' + str(self.mois) \
              + '&Usager=' + str(self.usager_id.cie_oaci)
        action = {
            'type': 'ir.actions.act_url',
            'name': _('Impression lettre d''accompagnement'),
            'url': url,
            'target': 'new',
        }
        if self.state not in '3la_imprime 4fg_imprime 5imprime':
            self.write({'state': '3la_imprime'})
        return action

    def imprimer_fg_periode(self):
        self.ensure_one()
        url = 'https://<login>:<mot_de_passe>@www.jasper.gov.pf/jasperserver/rest_v2/reports/Aviation_civile/Facture_globale.pdf'\
              + '?annee=' + str(self.annee) \
              + '&p_mois=' + str(self.mois) \
              + '&Usager=' + str(self.usager_id.cie_oaci)
        action = {
            'type': 'ir.actions.act_url',
            'name': _('Impression facture globale'),
            'url': url,
            'target': 'new',
        }
        if self.state not in '4fg_imprime 5imprime':
            self.write({'state': '4fg_imprime'})
        return action

    def imprimer_facture_periode(self):
        self.ensure_one()
        url = 'https://<login>:<mot_de_passe>@www.jasper.gov.pf/jasperserver/rest_v2/reports/Aviation_civile/manureva_facture.pdf'\
              + '?annee=' + str(self.annee) \
              + '&p_mois=' + str(self.mois) \
              + '&Usager=' + str(self.usager_id.cie_oaci)
        action = {
            'type': 'ir.actions.act_url',
            'name': _('Impression facture individuelle'),
            'url': url,
            'target': 'new',
        }
        if self.state != '5imprime':
            self.write({'state': '5imprime'})
        return action

    def facturer_periode(self):
        self.ensure_one()
        debut = datetime.strftime(date(self.annee, self.mois, 1), "%Y-%m-%d 00:00:00")
        fin = datetime.strftime(date(self.annee,
                                     self.mois,
                                     monthrange(self.annee,
                                                self.mois)[1]), "%Y-%m-%d 23:59:59")
        facture = 0
        self.env.cr.execute("select distinct aerodrome_id "
                            "from manureva_seac mv, manureva_type_aerodrome ta, manureva_aerodrome ad "
                            "where usager_id=%s "
                            "and EXTRACT( YEAR FROM date) = %s "
                            "and EXTRACT( MONTH FROM date) = %s "
                            "and mv.aerodrome_id = ad.id "
                            "and ad.type_aerodrome_id = ta.id "
                            "and ta.a_facturer "
                            "order by 1",
                            (self.usager_id.id, self.annee, self.mois,))
        aerodromes = self.env.cr.fetchall()
        for aerodrome in aerodromes:
            # Facture
            facture += 1
            seac = self.env['manureva.seac'].search([('aerodrome_id', '=', aerodrome[0]),
                                                     ('usager_id', '=', self.usager_id.id),
                                                     ('date', '>=', debut),
                                                     ('date', '<=', fin)
                                                     ], limit=1)
            f = self.env['manureva.facture'].create(
                {'facture': seac.date.strftime("%y") + seac.date.strftime("%m") + str(facture).zfill(3)
                    , 'name': seac.date.strftime("%m/%y_") + self.usager_id.cie_oaci + "_" + seac.aerodrome_id.name
                    , 'aerodrome_id': seac.aerodrome_id.id
                    , 'usager_id': self.usager_id.id
                    , 'periode_id': self.id
                 })
            type_aerodrome = self.env['manureva.aerodrome'].search([('name', '=', seac.aerodrome_id.name)],
                                                                   limit=1).type_aerodrome_id.name
            montant_balisage = self.env['manureva.balisage'].search([('type_aerodrome_id', '=', type_aerodrome),
                                                                     ('active', '=', True)],
                                                                    limit=1).montant
            apres_balisage = self.env['manureva.balisage'].search([('type_aerodrome_id', '=', type_aerodrome),
                                                                   ('active', '=', True)],
                                                                  limit=1).apres
            avant_balisage = self.env['manureva.balisage'].search([('type_aerodrome_id', '=', type_aerodrome),
                                                                   ('active', '=', True)],
                                                                  limit=1).avant

            atterrissage = 0
            passager = 0
            balisage = 0
            self.env.cr.execute(
                "select distinct type_aeronef_id from manureva_aeronef an, manureva_seac mv "
                "where mv.usager_id=%s and mv.date >= %s and mv.date <= %s order by 1",
                (seac.usager_id.id, debut, fin,))
            types = self.env.cr.fetchall()
            for type_aeronef in types:
                seacs = self.env['manureva.seac'].search([('aeronef_id.type_aeronef_id.id', '=',
                                                           type_aeronef[0]),
                                                          ('aerodrome_id', '=', aerodrome[0]),
                                                          ('usager_id', '=', self.usager_id.id),
                                                          ('date', '>=', debut),
                                                          ('date', '<=', fin)
                                                          ])
                atterrissage = 0
                passager = 0
                balisage = 0
                for seac in seacs:
                    # Atterrissage
                    if seac.mouvement == 'A':
                        mmd = max(2, ceil(self.env['manureva.type_aeronef'].search([('id', '=', type_aeronef[0])],
                                                                                   limit=1).tonnage))
                        tarif = self.env['manureva.param_att'].search([('debut', '<=', seac.date)
                                                                          , ('fin', '>=', seac.date)
                                                                          ,
                                                                       ('type_aerodrome_id', '=', type_aerodrome)
                                                                          , ('mmd_inf', '<', mmd)
                                                                          , ('mmd_sup', '>=', mmd)], limit=1)
                        atterrissage += tarif.base + tarif.coefficient * (mmd - tarif.correction)
                    # Passager
                    if seac.mouvement == 'D':
                        montant = self.env['manureva.param_pax'].search([('debut', '<=', seac.date)
                                                                            , ('fin', '>', seac.date)
                                                                            ,
                                                                         (
                                                                             'type_aerodrome_id', '=',
                                                                             type_aerodrome)],
                                                                        limit=1).montant
                        passager += montant * (seac.pax_plus - seac.pax_moins - seac.paxlnp1
                                               - seac.paxlnp2 - seac.paxlnp3 - seac.paxlnp4
                                               - seac.paxlnp5)
                    # Balisage
                    if seac.heure_decimale >= apres_balisage or seac.heure_decimale <= avant_balisage:
                        balisage += montant_balisage

                # Lignes de facture
                if atterrissage + passager + balisage > 0:
                    self.env['manureva.ligne_facture'].create({'facture_id': f.id
                                                                  , 'atterrissage': round(atterrissage)
                                                                  , 'passager': round(passager)
                                                                  , 'balisage': round(balisage)
                                                                  , 'type_aeronef_id': type_aeronef[0]
                                                               })
            # La période est facturée
            self.env['manureva.periode'].search([('id', '=', self.id)], limit=1).write(
                {'a_facturer': False, 'facture': True, 'state': '2facture'})

    @api.depends('a_facturer', 'facture')
    def _compute_state(self):
        for periode in self:
            if periode.facture_ids not in (False, None) and len(periode.facture_ids) > 0:
                periode.state = '2facture'
            else:
                periode.state = '1a_facturer'
            # if periode.state not in ('3la_imprime', '4fg_imprime', '5imprime'):
            #     if periode.facture:
            #         periode.state = '2facture'
            #     else:
            #         periode.state = '1a_facturer'

    def supprimer_facture_periode(self):
        # self.ensure_one()
        for periode in self:
            for facture in periode.facture_ids:
                periode.env['manureva.facture'].search([('id', '=', facture.id)]).unlink()
            periode.a_facturer = True
            periode.facture = False
            periode.state = '1a_facturer'

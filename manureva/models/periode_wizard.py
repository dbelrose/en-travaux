from odoo import fields, models, api
from datetime import datetime, date
from calendar import monthrange
from math import *


class PeriodeWizard(models.TransientModel):
    _name = 'manureva.periode_wizard'
    _description = 'Calculer les factures'

    def _get_default_periode(self):
        return self.env['manureva.periode'].browse(self.env.context.get('active_ids')) \
            .search([('a_facturer', '=', True),
                     ('id', 'in', self.env.context.get('active_ids'))])

    periode_ids = fields.Many2many(
        comodel_name='manureva.periode',
        string='Période',
        default=_get_default_periode,
    )

    def facturer_periode(self):
        for periode in self.periode_ids:
            debut = datetime.strftime(date(periode.annee, periode.mois, 1), "%Y-%m-%d 00:00:00")
            fin = datetime.strftime(date(periode.annee,
                                         periode.mois,
                                         monthrange(periode.annee,
                                                    periode.mois)[1]), "%Y-%m-%d 23:59:59")
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
                                (periode.usager_id.id, periode.annee, periode.mois,))
            aerodromes = self.env.cr.fetchall()
            for aerodrome in aerodromes:
                # Facture
                facture += 1
                seac = self.env['manureva.seac'].search([('aerodrome_id', '=', aerodrome[0]),
                                                         ('usager_id', '=', periode.usager_id.id),
                                                         ('date', '>=', debut),
                                                         ('date', '<=', fin)
                                                         ], limit=1)
                f = self.env['manureva.facture'].create(
                    {'facture': seac.date.strftime("%y") + seac.date.strftime("%m") + str(facture).zfill(3)
                        , 'name': seac.date.strftime("%m/%y_") + periode.usager_id.cie_oaci + "_" + seac.aerodrome_id.name
                        , 'aerodrome_id': seac.aerodrome_id.id
                        , 'usager_id': periode.usager_id.id
                        , 'periode_id': periode.id
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
                                                              ('usager_id', '=', periode.usager_id.id),
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
                    # ===============================================================================================
                    # Comme il est difficile d'obtenir les informations en provenance des aérodromes, le calcul de la
                    # redevance balisage est désormais uniquement calculée selon la paramétrage horaire.

                        # Balisage
                        if seac.heure_decimale >= apres_balisage or seac.heure_decimale <= avant_balisage:
                            balisage += montant_balisage

                    # Vols publics aérodromes
                    #
                    # vpas = self.env['manureva.vol_public_aerodrome'].search([('fc27.type_aeronef_id.id', '=',
                    #                                            type_aeronef[0]),
                    #                                           ('fc02', '=', aerodrome[0]),
                    #                                           ('fc03', '=', periode.usager_id.id),
                    #                                           ('fc32', '>=', debut),
                    #                                           ('fc32', '<=', fin)
                    #                                           ])
                    # balisage = 0
                    # for vpa in vpas:
                    #     # Balisage
                    #     if vpa.fc43 == 'S':
                    #         balisage += montant_balisage
                    # ===============================================================================================

                    # Lignes de facture
                    if atterrissage + passager + balisage > 0:
                        self.env['manureva.ligne_facture'].create({'facture_id': f.id
                                                                      , 'atterrissage': round(atterrissage)
                                                                      , 'passager': round(passager)
                                                                      , 'balisage': round(balisage)
                                                                      , 'type_aeronef_id': type_aeronef[0]
                                                                   })
                # La période est facturée
                self.env['manureva.periode'].search([('id', '=', periode.id)], limit=1).write(
                    {'a_facturer': False, 'facture': True})

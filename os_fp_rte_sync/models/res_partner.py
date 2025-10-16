
# -*- coding: utf-8 -*-
from odoo import fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    x_tahiti = fields.Char("N° TAHITI", index=True)
    x_etablissement = fields.Char("N° Établissement (RTE)", index=True)
    x_forme_juridique = fields.Char("Forme juridique")  # conservé pour info brute
    x_naf = fields.Char("Code NAF/APE")
    x_effectif_classe = fields.Char("Classe d'effectifs")
    x_archipel = fields.Char("Archipel / Île")
    x_date_creation = fields.Date("Date de création (RTE)")
    x_rte_updated_at = fields.Datetime("Dernière maj RTE")

    _sql_constraints = [
        ("uniq_etablissement", "unique(x_etablissement)", "Le N° d'établissement RTE doit être unique."),
    ]

# ("uniq_tahiti", "unique(x_tahiti)", "Le N° TAHITI doit être unique sur les partenaires."),

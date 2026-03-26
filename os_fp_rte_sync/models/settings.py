
# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fp_rte_import_only_active = fields.Boolean(
        string="N'importer que les entreprises actives",
        default=True,
        config_parameter="fp_rte_sync.import_only_active",
    )
    fp_rte_naf_whitelist = fields.Char(
        string="Codes NAF/APE à considérer (liste blanche)",
        help="Codes séparés par des virgules. Joker * supporté (ex : 56.*, 47.5*).",
        config_parameter="fp_rte_sync.naf_whitelist",
    )

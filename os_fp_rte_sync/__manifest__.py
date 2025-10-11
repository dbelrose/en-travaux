
# -*- coding: utf-8 -*-
{
    "name": "OS FP RTE Sync (ISPF → res.partner) — V1.1",
    "summary": "RTE (ISPF) → Contacts: entreprises/établissements, tags APE/Effectif, company type OCA, ID numbers OCA, effectif range OCA, pliage single ETAB, BG one-shot",
    "version": "17.1.1",
    "category": "Contacts",
    "author": "Didier BELROSE & contribut.",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "partner_company_type",
        "partner_identification",
        "partner_employee_quantity"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "views/rte_sync_views.xml",
        "views/res_config_settings_view.xml"
    ],
    "installable": True,
    "application": False
}

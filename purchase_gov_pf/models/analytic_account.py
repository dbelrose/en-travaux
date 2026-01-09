# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.depends('group_id')
    def _compute_is_project(self):
        group_project = self.env.ref('purchase_gov_pf.analytic_group_projects', False)\
            and self.env.ref('purchase_gov_pf.analytic_group_projects')
        for account in self:
            if account.group_id == group_project:
                account.is_project = True
            else:
                account.is_project = False

    is_project = fields.Boolean(string='Is a Project',
                                store=True,
                                compute='_compute_is_project')

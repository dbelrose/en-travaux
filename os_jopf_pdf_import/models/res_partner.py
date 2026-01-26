from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    jopf_import_ids = fields.Many2many('jopf.import', 'jopf_import_partner_rel',
                                       'partner_id', 'import_id', string='Imports JOPF')
    jopf_import_count = fields.Integer(compute='_compute_jopf_import_count')

    def _compute_jopf_import_count(self):
        for p in self:
            p.jopf_import_count = len(p.jopf_import_ids)

    def action_view_jopf_imports(self):
        return {
            'name': _('Imports JOPF'),
            'type': 'ir.actions.act_window',
            'res_model': 'jopf.import',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.jopf_import_ids.ids)],
        }

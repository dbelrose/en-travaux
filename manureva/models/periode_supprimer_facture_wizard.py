from odoo.exceptions import ValidationError
from odoo import fields, models, api, _


class PeriodeSupprimerFactureWizard(models.TransientModel):
    _name = 'manureva.periode_supprimer_facture_wizard'
    _description = 'Supprimer les factures'

    def _get_default_periode(self):
        return self.env['manureva.periode'].browse(self.env.context.get('active_ids')) \
            .search([('state', '=', '2facture'),
                     ('id', 'in', self.env.context.get('active_ids'))])

    periode_ids = fields.Many2many(
        comodel_name='manureva.periode',
        string='Périodes',
        default=_get_default_periode,
    )

    def supprimer_facture_periode(self):
        for periode in self.periode_ids:
            for facture in periode.facture_ids:
                self.env['manureva.facture'].search([('id', '=', facture.id)]).unlink()
            self.env['manureva.periode'].search([('id', '=', periode.id)]).write({'a_facturer': True,
                                                                                  'facture': False,
                                                                                  'state': '1a_facturer'})

    @api.constrains('periode_ids')
    def _check_periode_ids(self):
        if self.periode_ids.search_count([('state', '!=', '2facture')]) > 0:
            raise ValidationError(_('Attention! Au moins une période n''a pas été facturée ou est déjà imprimée.'))

from odoo.exceptions import ValidationError
from odoo import fields, models, api, _


class PeriodeImprimerFactureWizard(models.TransientModel):
    _name = 'manureva.periode_imprimer_facture_wizard'
    _description = 'Imprimer les factures'

    def _get_default_periode(self):
        return self.env['manureva.periode'].browse(self.env.context.get('active_ids')) \
            .search([('state', '=', '2facture'),
                     ('id', 'in', self.env.context.get('active_ids'))],
                    limit=1)

    periode_ids = fields.Many2many(
        comodel_name='manureva.periode',
        string='Périodes',
        default=_get_default_periode,
    )

    def imprimer_facture_periode(self):
        self.ensure_one()
        for periode_id in self.periode_ids:
            url = 'https://<login>:<mot_de_passe>@www.jasper.gov.pf/jasperserver/rest_v2/reports/Aviation_civile/manureva_facture.pdf'\
                  + '?annee=' + str(periode_id.annee) \
                  + '&p_mois=' + str(periode_id.mois) \
                  + '&Usager=' + str(periode_id.usager_id.cie_oaci)
            action = {
                'type': 'ir.actions.act_url',
                'name': _('Impression facture individuelle'),
                'url': url,
                'target': 'new',
            }
            self.env['manureva.periode'].search([('id', '=', periode_id.id)]).write({'state': '5imprime'})
            return action

    @api.constrains('periode_ids')
    def _check_periode_ids(self):
        if len(self.periode_ids.ids) > 1:
            raise ValidationError(_('Attention! Une seule période à la fois.'))
        if self.periode_ids.search_count([('state', '=', '1a_facturer')]) > 0:
            raise ValidationError(_('Attention! La période n''a pas été facturée.'))

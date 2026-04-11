from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardBordereau(models.TransientModel):
    _name = 'cps.wizard.bordereau'
    _description = 'Assistant de génération de bordereau mensuel'

    praticien_id = fields.Many2one('cps.praticien', string='Praticien', required=True)
    mois = fields.Selection([
        ('01', 'Janvier'), ('02', 'Février'), ('03', 'Mars'),
        ('04', 'Avril'), ('05', 'Mai'), ('06', 'Juin'),
        ('07', 'Juillet'), ('08', 'Août'), ('09', 'Septembre'),
        ('10', 'Octobre'), ('11', 'Novembre'), ('12', 'Décembre'),
    ], string='Mois', required=True)
    annee = fields.Char(string='Année', required=True, default=lambda self: str(fields.Date.today().year))
    feuille_ids = fields.Many2many('cps.feuille.soins', string='Feuilles à inclure',
                                    domain="[('praticien_id','=',praticien_id),('state','=','confirmed'),('bordereau_id','=',False)]")

    @api.onchange('praticien_id', 'mois', 'annee')
    def _onchange_load_feuilles(self):
        if self.praticien_id and self.mois and self.annee:
            feuilles = self.env['cps.feuille.soins'].search([
                ('praticien_id', '=', self.praticien_id.id),
                ('state', '=', 'confirmed'),
                ('bordereau_id', '=', False),
            ])
            self.feuille_ids = feuilles

    def action_generate(self):
        self.ensure_one()
        if not self.feuille_ids:
            raise UserError(_('Aucune feuille de soins sélectionnée.'))

        mois_labels = dict(self._fields['mois'].selection)
        mois_str = f"{mois_labels[self.mois]} {self.annee}"

        bordereau = self.env['cps.bordereau'].create({
            'praticien_id': self.praticien_id.id,
            'mois': mois_str,
            'date_bordereau': fields.Date.today(),
        })
        self.feuille_ids.write({'bordereau_id': bordereau.id})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Bordereau généré'),
            'res_model': 'cps.bordereau',
            'res_id': bordereau.id,
            'view_mode': 'form',
        }

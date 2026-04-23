import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardBordereau(models.TransientModel):
    _name = 'cps.wizard.bordereau'
    _description = 'Assistant de génération de bordereau mensuel'

    @api.model
    def _default_praticien(self):
        return self.env['res.partner'].search(
            [('user_id', '=', self.env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1,
        )

    @api.model
    def _earliest_confirmed_feuille(self, praticien):
        if not praticien:
            return self.env['cps.feuille.soins']
        return self.env['cps.feuille.soins'].search([
            ('praticien_id', '=', praticien.id),
            ('state', '=', 'confirmed'),
            ('bordereau_id', '=', False),
            ('date_prescription', '!=', False),
        ], order='date_prescription asc', limit=1)

    @api.model
    def _default_mois(self):
        praticien = self._default_praticien()
        feuille = self._earliest_confirmed_feuille(praticien)
        if feuille:
            return str(feuille.date_prescription.month).zfill(2)
        return str(datetime.date.today().month).zfill(2)

    @api.model
    def _default_annee(self):
        praticien = self._default_praticien()
        feuille = self._earliest_confirmed_feuille(praticien)
        if feuille:
            return str(feuille.date_prescription.year)
        return str(datetime.date.today().year)

    @api.model
    def _default_feuilles(self):
        praticien = self._default_praticien()
        if not praticien:
            return self.env['cps.feuille.soins']
        return self.env['cps.feuille.soins'].search([
            ('praticien_id', '=', praticien.id),
            ('state', '=', 'confirmed'),
            ('bordereau_id', '=', False),
        ])

    praticien_id = fields.Many2one(
        'res.partner', string='Praticien',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        required=True, default=_default_praticien,
    )
    mois = fields.Selection([
        ('01', 'Janvier'), ('02', 'Février'), ('03', 'Mars'),
        ('04', 'Avril'), ('05', 'Mai'), ('06', 'Juin'),
        ('07', 'Juillet'), ('08', 'Août'), ('09', 'Septembre'),
        ('10', 'Octobre'), ('11', 'Novembre'), ('12', 'Décembre'),
    ], required=True, default=_default_mois)
    annee = fields.Char(required=True, default=_default_annee)
    feuille_ids = fields.Many2many(
        'cps.feuille.soins', string='Feuilles à inclure',
        domain="[('praticien_id','=',praticien_id),('state','=','confirmed'),('bordereau_id','=',False)]",
        default=_default_feuilles,
    )

    @api.onchange('praticien_id', 'mois', 'annee')
    def _onchange_load_feuilles(self):
        if self.praticien_id and self.mois and self.annee:
            self.feuille_ids = self.env['cps.feuille.soins'].search([
                ('praticien_id', '=', self.praticien_id.id),
                ('state', '=', 'confirmed'),
                ('bordereau_id', '=', False),
            ])

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

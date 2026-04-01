from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CpsPatient(models.Model):
    _name = 'cps.patient'
    _description = 'Patient / Bénéficiaire CPS'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'

    nom = fields.Char(string='Nom', required=True)
    prenom = fields.Char(string='Prénom', required=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    dn = fields.Char(string='Numéro DN (matricule)', required=True,
                     help='Numéro d\'identification CPS du patient')
    date_naissance = fields.Date(string='Date de naissance')

    # Assuré si différent du bénéficiaire
    est_assure = fields.Boolean(string='Est l\'assuré(e)', default=True)
    assure_nom = fields.Char(string='Nom de l\'assuré')
    assure_prenom = fields.Char(string='Prénom de l\'assuré')
    assure_dn = fields.Char(string='DN de l\'assuré')

    adresse = fields.Char(string='Adresse')
    tel = fields.Char(string='Téléphone')
    active = fields.Boolean(default=True)

    feuille_soins_ids = fields.One2many('cps.feuille.soins', 'patient_id', string='Feuilles de soins')
    feuille_count = fields.Integer(compute='_compute_feuille_count')

    @api.depends('nom', 'prenom')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.nom} {rec.prenom}".strip().upper()

    @api.depends('feuille_soins_ids')
    def _compute_feuille_count(self):
        for rec in self:
            rec.feuille_count = len(rec.feuille_soins_ids)

    @api.constrains('dn')
    def _check_dn(self):
        for rec in self:
            if rec.dn and len(rec.dn.replace(' ', '')) < 5:
                raise ValidationError(_('Le numéro DN doit comporter au moins 5 caractères.'))

    def action_view_feuilles(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feuilles de soins',
            'res_model': 'cps.feuille.soins',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
        }

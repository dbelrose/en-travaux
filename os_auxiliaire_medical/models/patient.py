from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CpsPatient(models.Model):
    _name = 'cps.patient'
    _description = 'Patient / Bénéficiaire CPS'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread']
    _rec_name = 'name'

    partner_id = fields.Many2one(
        'res.partner', string='Contact Odoo', required=True,
        ondelete='cascade', auto_join=True,
    )

    nom = fields.Char(related='partner_id.lastname', readonly=False, store=True,
                       required=True, tracking=True)
    prenom = fields.Char(related='partner_id.firstname', readonly=False, store=True,
                          required=True, tracking=True)
    date_naissance = fields.Date(related='partner_id.birthdate_date',
                                  readonly=False, store=True)

    dn = fields.Char(string='Numéro DN (matricule)', required=True)
    est_assure = fields.Boolean(string="Est l'assuré(e)", default=True)
    assure_nom = fields.Char(string="Nom de l'assuré")
    assure_prenom = fields.Char(string="Prénom de l'assuré")
    assure_dn = fields.Char(string="DN de l'assuré")
    active = fields.Boolean(default=True)

    company_id = fields.Many2one('res.company', required=True,
                                  default=lambda self: self.env.company, index=True)
    feuille_count = fields.Integer(compute='_compute_feuille_count', string='Feuilles')

    @api.depends('partner_id')
    def _compute_feuille_count(self):
        FeuilleSoins = self.env['cps.feuille.soins']
        for rec in self:
            rec.feuille_count = FeuilleSoins.search_count(
                [('patient_id', '=', rec.partner_id.id)]
            ) if rec.partner_id else 0

    @api.constrains('dn')
    def _check_dn(self):
        for rec in self:
            if rec.dn and len(rec.dn.replace(' ', '')) < 5:
                raise ValidationError(_('Le numéro DN doit comporter au moins 5 caractères.'))

    # ── Tagger le partenaire "Patient CPS" ────────────────────────────────────

    def _tag_patient(self):
        cat = self.env.ref(
            'os_auxiliaire_medical.partner_category_patient', raise_if_not_found=False
        )
        if cat and self.partner_id:
            self.partner_id.write({'category_id': [(4, cat.id)]})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id'):
                partner = self.env['res.partner'].create({
                    'lastname': vals.get('nom', ''),
                    'firstname': vals.get('prenom', ''),
                    'birthdate_date': vals.get('date_naissance'),
                    'is_company': False,
                    'customer_rank': 0,
                })
                vals['partner_id'] = partner.id
        records = super().create(vals_list)
        records._tag_patient()
        return records

    def action_view_feuilles(self):
        return {'type': 'ir.actions.act_window', 'name': 'Feuilles de soins',
                'res_model': 'cps.feuille.soins', 'view_mode': 'list,form',
                'domain': [('patient_id', '=', self.partner_id.id)]}


from odoo import models, fields, api


class CpsPraticien(models.Model):
    _name = 'cps.praticien'
    _description = 'Auxiliaire médical / Praticien CPS'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom complet', required=True, tracking=True)
    code_auxiliaire = fields.Char(string='Code auxiliaire médical', required=True, tracking=True,
                                   help='Code CPS obligatoire (ex: O233)')
    profession = fields.Selection([
        ('kinesitherapeute', 'Masseur-kinésithérapeute'),
        ('orthophoniste', 'Orthophoniste'),
        ('orthoptiste', 'Orthoptiste'),
        ('pedicure', 'Pédicure-Podologue'),
        ('infirmier', 'Infirmier(e)'),
        ('autre', 'Autre'),
    ], string='Profession', required=True, default='orthophoniste')
    tel = fields.Char(string='Téléphone')
    bp = fields.Char(string='BP / Adresse')
    email = fields.Char(string='Email')
    active = fields.Boolean(default=True)

    feuille_soins_ids = fields.One2many('cps.feuille.soins', 'praticien_id', string='Feuilles de soins')
    bordereau_ids = fields.One2many('cps.bordereau', 'praticien_id', string='Bordereaux')

    feuille_count = fields.Integer(compute='_compute_counts', string='Feuilles')
    bordereau_count = fields.Integer(compute='_compute_counts', string='Bordereaux')

    @api.depends('feuille_soins_ids', 'bordereau_ids')
    def _compute_counts(self):
        for rec in self:
            rec.feuille_count = len(rec.feuille_soins_ids)
            rec.bordereau_count = len(rec.bordereau_ids)

    def action_view_feuilles(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feuilles de soins',
            'res_model': 'cps.feuille.soins',
            'view_mode': 'list,form',
            'domain': [('praticien_id', '=', self.id)],
        }

    def action_view_bordereaux(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bordereaux',
            'res_model': 'cps.bordereau',
            'view_mode': 'list,form',
            'domain': [('praticien_id', '=', self.id)],
        }

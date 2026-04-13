from odoo import models, fields, api


class CpsPraticien(models.Model):
    _name = 'cps.praticien'
    _description = 'Auxiliaire médical / Praticien CPS'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom complet', required=True, tracking=True)
    code_auxiliaire = fields.Char(
        string='Code auxiliaire médical', required=True, tracking=True,
        help='Code CPS obligatoire (ex: O233)',
    )
    profession = fields.Selection([
        ('kinesitherapeute', 'Masseur-kinésithérapeute'),
        ('orthophoniste', 'Orthophoniste'),
        ('orthoptiste', 'Orthoptiste'),
        ('pedicure', 'Pédicure-Podologue'),
        ('infirmier', 'Infirmier(e)'),
        ('autre', 'Autre'),
    ], string='Profession', required=True, default='orthophoniste')

    # Liaison avec l'utilisateur Odoo
    user_id = fields.Many2one(
        'res.users', string='Utilisateur Odoo',
        help='Associer ce praticien à un utilisateur pour pré-remplir les feuilles de soins.',
        ondelete='set null',
    )

    # Coordonnées — synchronisables depuis le partenaire de l'utilisateur
    tel = fields.Char(string='Téléphone')
    bp = fields.Char(string='BP / Adresse')
    email = fields.Char(string='Email')
    active = fields.Boolean(default=True)

    # ── Multi-company ───────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    feuille_soins_ids = fields.One2many(
        'cps.feuille.soins', 'praticien_id', string='Feuilles de soins',
    )
    bordereau_ids = fields.One2many(
        'cps.bordereau', 'praticien_id', string='Bordereaux',
    )

    feuille_count = fields.Integer(compute='_compute_counts', string='Feuilles')
    bordereau_count = fields.Integer(compute='_compute_counts', string='Bordereaux')

    @api.depends('feuille_soins_ids', 'bordereau_ids')
    def _compute_counts(self):
        for rec in self:
            rec.feuille_count = len(rec.feuille_soins_ids)
            rec.bordereau_count = len(rec.bordereau_ids)

    @api.onchange('user_id')
    def _onchange_user_id(self):
        """Pré-remplit les coordonnées depuis le partenaire de l'utilisateur."""
        if self.user_id and self.user_id.partner_id:
            partner = self.user_id.partner_id
            if not self.name:
                self.name = partner.name
            if not self.tel:
                self.tel = partner.phone or partner.mobile
            if not self.email:
                self.email = partner.email

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

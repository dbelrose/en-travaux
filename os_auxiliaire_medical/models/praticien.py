from odoo import models, fields, api

# Map profession → xmlid de la catégorie partenaire
PROFESSION_CATEGORY_XMLID = {
    'kinesitherapeute': 'os_auxiliaire_medical.partner_category_kinesitherapeute',
    'orthophoniste':    'os_auxiliaire_medical.partner_category_orthophoniste',
    'orthoptiste':      'os_auxiliaire_medical.partner_category_orthoptiste',
    'pedicure':         'os_auxiliaire_medical.partner_category_pedicure',
    'infirmier':        'os_auxiliaire_medical.partner_category_infirmier',
    'autre':            'os_auxiliaire_medical.partner_category_autre_praticien',
}


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

    # Utilisateur Odoo associé – par défaut l'utilisateur connecté
    user_id = fields.Many2one(
        'res.users', string='Utilisateur Odoo',
        ondelete='set null',
        default=lambda self: self.env.user,
    )

    # Lien vers res.partner (pour partage avec l'annuaire Odoo)
    partner_id = fields.Many2one(
        'res.partner', string='Contact Odoo',
        ondelete='set null',
        help='Contact partenaire associé (tagué automatiquement "Praticien CPS").',
    )

    tel = fields.Char(string='Téléphone')
    bp = fields.Char(string='BP / Adresse')
    email = fields.Char(string='Email')
    active = fields.Boolean(default=True)

    company_id = fields.Many2one(
        'res.company', string='Société', required=True,
        default=lambda self: self.env.company, index=True,
    )

    feuille_count = fields.Integer(compute='_compute_counts', string='Feuilles')
    bordereau_count = fields.Integer(compute='_compute_counts', string='Bordereaux')

    @api.depends('partner_id')
    def _compute_counts(self):
        FeuilleSoins = self.env['cps.feuille.soins']
        Bordereau = self.env['cps.bordereau']
        for rec in self:
            if rec.partner_id:
                rec.feuille_count = FeuilleSoins.search_count(
                    [('praticien_id', '=', rec.partner_id.id)]
                )
                rec.bordereau_count = Bordereau.search_count(
                    [('praticien_id', '=', rec.partner_id.id)]
                )
            else:
                rec.feuille_count = 0
                rec.bordereau_count = 0

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id and self.user_id.partner_id:
            partner = self.user_id.partner_id
            if not self.name:
                self.name = partner.name
            if not self.tel:
                self.tel = partner.phone or partner.mobile
            if not self.email:
                self.email = partner.email

    # ── Tagger le partenaire à la création/modification ───────────────────────

    def _get_profession_category(self):
        """Retourne la catégorie res.partner correspondant à la profession."""
        self.ensure_one()
        xmlid = PROFESSION_CATEGORY_XMLID.get(self.profession)
        if xmlid:
            try:
                return self.env.ref(xmlid)
            except Exception:
                pass
        return None

    def _tag_partner(self, partner):
        """Ajoute les catégories Praticien CPS + profession sur le partenaire."""
        if not partner:
            return
        cat_praticien = self.env.ref(
            'os_auxiliaire_medical.partner_category_praticien', raise_if_not_found=False
        )
        cat_profession = self._get_profession_category()
        cats_to_add = [c for c in [cat_praticien, cat_profession] if c]
        if cats_to_add:
            partner.write({'category_id': [(4, c.id) for c in cats_to_add]})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.user_id and rec.user_id.partner_id and not rec.partner_id:
                rec.partner_id = rec.user_id.partner_id
            rec._tag_partner(rec.partner_id)
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'profession' in vals or 'partner_id' in vals:
            for rec in self:
                rec._tag_partner(rec.partner_id)
        return res

    def action_view_feuilles(self):
        return {'type': 'ir.actions.act_window', 'name': 'Feuilles de soins',
                'res_model': 'cps.feuille.soins', 'view_mode': 'list,form',
                'domain': [('praticien_id', '=', self.partner_id.id)]}

    def action_view_bordereaux(self):
        return {'type': 'ir.actions.act_window', 'name': 'Bordereaux',
                'res_model': 'cps.bordereau', 'view_mode': 'list,form',
                'domain': [('praticien_id', '=', self.partner_id.id)]}

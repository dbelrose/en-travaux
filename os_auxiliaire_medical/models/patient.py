from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CpsPatient(models.Model):
    _name = 'cps.patient'
    _description = 'Patient / Bénéficiaire CPS'
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread']
    _rec_name = 'display_name'

    # ── Lien de délégation ──────────────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner', string='Contact Odoo', required=True,
        ondelete='cascade', auto_join=True,
        help='Sélectionnez un contact existant ou laissez vide : '
             'un nouveau contact sera créé automatiquement à l\'enregistrement.',
    )

    # ── Champs CPS mappés sur res.partner (partner_firstname + partner_birthdate) ──
    nom = fields.Char(
        string='Nom',
        related='partner_id.lastname', readonly=False, store=True,
        required=True, tracking=True,
    )
    prenom = fields.Char(
        string='Prénom',
        related='partner_id.firstname', readonly=False, store=True,
        required=True, tracking=True,
    )
    date_naissance = fields.Date(
        string='Date de naissance',
        related='partner_id.birthdate_date', readonly=False, store=True,
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    # ── Champs propres CPS ─────────────────────────────────────────────────
    dn = fields.Char(
        string='Numéro DN (matricule)', required=True,
        help="Numéro d'identification CPS du patient",
    )

    est_assure = fields.Boolean(string="Est l'assuré(e)", default=True)
    assure_nom = fields.Char(string="Nom de l'assuré")
    assure_prenom = fields.Char(string="Prénom de l'assuré")
    assure_dn = fields.Char(string="DN de l'assuré")

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
        'cps.feuille.soins', 'patient_id', string='Feuilles de soins',
    )
    feuille_count = fields.Integer(compute='_compute_feuille_count')

    # ── Calculs ─────────────────────────────────────────────────────────────

    @api.depends('nom', 'prenom')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.nom or ''} {rec.prenom or ''}".strip().upper()

    @api.depends('feuille_soins_ids')
    def _compute_feuille_count(self):
        for rec in self:
            rec.feuille_count = len(rec.feuille_soins_ids)

    # ── Contraintes ─────────────────────────────────────────────────────────

    @api.constrains('dn')
    def _check_dn(self):
        for rec in self:
            if rec.dn and len(rec.dn.replace(' ', '')) < 5:
                raise ValidationError(
                    _('Le numéro DN doit comporter au moins 5 caractères.')
                )

    # ── Création ────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('partner_id'):
                # Pas de contact sélectionné : création automatique d'un partenaire
                # en alimentant directement firstname/lastname.
                partner = self.env['res.partner'].create({
                    'lastname': vals.get('nom', ''),
                    'firstname': vals.get('prenom', ''),
                    'birthdate_date': vals.get('date_naissance'),
                    'is_company': False,
                    'customer_rank': 0,
                })
                vals['partner_id'] = partner.id
        return super().create(vals_list)

    # ── Actions ─────────────────────────────────────────────────────────────

    def action_view_feuilles(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Feuilles de soins',
            'res_model': 'cps.feuille.soins',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
        }

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime
import pytz


def _tahiti_today_short():
    tz = pytz.timezone('Pacific/Tahiti')
    return datetime.datetime.now(tz).strftime('%d/%m/%y')


def _upper_name(partner):
    return (partner.name or '').upper() if partner else ''


def _format_amount_comma(amount):
    if amount == int(amount):
        return '{:,.0f}'.format(int(amount)).replace(',', '\u202f')
    return '{:,.2f}'.format(amount).replace(',', '\u202f').replace('.', ',')


class CpsBordereau(models.Model):
    _name = 'cps.bordereau'
    _description = 'Bordereau de facturation mensuel CPS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_bordereau desc'

    name = fields.Char(string='N° Bordereau', required=True, copy=False,
                       default=lambda self: _('Nouveau'), tracking=True)

    praticien_id = fields.Many2one(
        'res.partner', string='Praticien',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        required=True, tracking=True, ondelete='restrict',
    )
    date_bordereau = fields.Date(string='Date du bordereau', required=True,
                                 default=fields.Date.today, tracking=True)
    mois = fields.Char(string='Mois / Période', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'), ('validated', 'Validé'),
        ('submitted', 'Transmis CPS'), ('closed', 'Clôturé'),
    ], default='draft', tracking=True)

    feuille_ids = fields.One2many(
        'cps.feuille.soins', 'bordereau_id', string='Feuilles de soins',
    )
    nb_feuilles   = fields.Integer(compute='_compute_totaux', store=True)
    total_cps     = fields.Float(compute='_compute_totaux', store=True, digits=(12, 0))
    total_patient = fields.Float(compute='_compute_totaux', store=True, digits=(12, 0))
    total_general = fields.Float(compute='_compute_totaux', store=True, digits=(12, 0))
    notes = fields.Text()

    company_id = fields.Many2one(
        'res.company', required=True,
        default=lambda self: self.env.company, index=True,
    )

    # ── AJOUT : modèle de document ─────────────────────────────────────────────
    modele_id = fields.Many2one(
        'cps.bordereau.modele',
        string='Modèle de document',
        help='Gabarit utilisé pour la génération du PDF. '
             'Pré-rempli avec le modèle par défaut de la société.',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    modele_entete  = fields.Text(related='modele_id.entete_texte',       readonly=True)
    modele_pied    = fields.Text(related='modele_id.pied_page_texte',    readonly=True)
    modele_couleur = fields.Char(related='modele_id.couleur_principale', readonly=True)
    # ──────────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('cps.bordereau')
                    or _('Nouveau')
                )
            # Pré-sélection automatique du modèle par défaut
            if not vals.get('modele_id'):
                company_id = vals.get('company_id') or self.env.company.id
                company = self.env['res.company'].browse(company_id)
                modele = self.env['cps.bordereau.modele'].get_default_modele(
                    company=company
                )
                if modele:
                    vals['modele_id'] = modele.id
        return super().create(vals_list)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            modele = self.env['cps.bordereau.modele'].get_default_modele(
                company=self.company_id
            )
            self.modele_id = modele or False

    @api.depends('feuille_ids.montant_total', 'feuille_ids.montant_tiers_payant',
                 'feuille_ids.montant_patient')
    def _compute_totaux(self):
        for rec in self:
            rec.nb_feuilles   = len(rec.feuille_ids)
            rec.total_cps     = sum(rec.feuille_ids.mapped('montant_tiers_payant'))
            rec.total_patient = sum(rec.feuille_ids.mapped('montant_patient'))
            rec.total_general = rec.total_cps + rec.total_patient

    def action_validate(self):
        for rec in self:
            if not rec.feuille_ids:
                raise UserError(
                    _('Impossible de valider un bordereau sans feuilles de soins.')
                )
            rec.feuille_ids.action_submit()
            rec.state = 'validated'

    def action_submit_cps(self):
        self.state = 'submitted'

    def action_close(self):
        self.state = 'closed'

    def action_reset_draft(self):
        self.state = 'draft'

    def action_view_feuilles(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Feuilles de soins'),
            'res_model': 'cps.feuille.soins',
            'view_mode': 'list,form',
            'domain': [('bordereau_id', '=', self.id)],
            'context': {'default_bordereau_id': self.id},
        }

    def action_print_bordereau(self):
        return self.env.ref(
            'os_auxiliaire_medical.action_report_bordereau'
        ).report_action(self)

    def action_export_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/cps/bordereau/{self.id}/xlsx',
            'target': 'new',
        }

    def get_lignes_for_report(self):
        lignes = []
        for i, feuille in enumerate(
            self.feuille_ids.sorted('date_debut_soins'), start=1
        ):
            p = feuille.patient_id
            lignes.append({
                'n': i,
                'nom_prenom': f"{p.lastname or ''} {p.firstname or ''}".strip(),
                'dn': p.vat or '',
                'date_debut': (
                    feuille.date_debut_soins.strftime('%d/%m/%y')
                    if feuille.date_debut_soins else ''
                ),
                'date_fin': (
                    feuille.date_fin_soins.strftime('%d/%m/%y')
                    if feuille.date_fin_soins else ''
                ),
                'montant_cps':     feuille.montant_tiers_payant,
                'montant_patient': feuille.montant_patient,
                'montant_total':   feuille.montant_total,
            })
        return lignes

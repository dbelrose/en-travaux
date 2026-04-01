from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime


class CpsBordereau(models.Model):
    _name = 'cps.bordereau'
    _description = 'Bordereau de facturation mensuel CPS'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_bordereau desc'

    name = fields.Char(string='N° Bordereau', required=True, copy=False,
                        default=lambda self: _('Nouveau'), tracking=True)
    praticien_id = fields.Many2one('cps.praticien', string='Praticien', required=True,
                                    tracking=True, ondelete='restrict')
    date_bordereau = fields.Date(string='Date du bordereau', required=True,
                                  default=fields.Date.today, tracking=True)
    mois = fields.Char(string='Mois / Période', required=True,
                        help='Ex: Février 2026', tracking=True)
    annee = fields.Integer(string='Année', compute='_compute_annee_mois_num', store=True)
    mois_num = fields.Integer(string='Mois (num)', compute='_compute_annee_mois_num', store=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('validated', 'Validé'),
        ('submitted', 'Transmis CPS'),
        ('closed', 'Clôturé'),
    ], string='État', default='draft', tracking=True)

    feuille_ids = fields.One2many('cps.feuille.soins', 'bordereau_id', string='Feuilles de soins')
    nb_feuilles = fields.Integer(compute='_compute_totaux', string='Nb feuilles', store=True)

    total_cps = fields.Float(string='Total CPS', compute='_compute_totaux', store=True,
                              digits=(12, 0))
    total_patient = fields.Float(string='Total Patient', compute='_compute_totaux', store=True,
                                  digits=(12, 0))
    total_general = fields.Float(string='Total général', compute='_compute_totaux', store=True,
                                  digits=(12, 0))

    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cps.bordereau') or _('Nouveau')
        return super().create(vals_list)

    @api.depends('date_bordereau')
    def _compute_annee_mois_num(self):
        for rec in self:
            if rec.date_bordereau:
                rec.annee = rec.date_bordereau.year
                rec.mois_num = rec.date_bordereau.month
            else:
                rec.annee = 0
                rec.mois_num = 0

    @api.depends('feuille_ids.montant_total', 'feuille_ids.montant_tiers_payant',
                 'feuille_ids.montant_patient', 'feuille_ids.state')
    def _compute_totaux(self):
        for rec in self:
            feuilles_actives = rec.feuille_ids.filtered(lambda f: f.state != 'cancelled')
            rec.nb_feuilles = len(feuilles_actives)
            rec.total_cps = sum(feuilles_actives.mapped('montant_tiers_payant'))
            rec.total_patient = sum(feuilles_actives.mapped('montant_patient'))
            rec.total_general = rec.total_cps + rec.total_patient

    @api.model
    def _get_or_create_bordereau(self, praticien_id, annee, mois):
        """Retourne le bordereau du mois/année pour ce praticien, le crée si absent."""
        bordereau = self.search([
            ('praticien_id', '=', praticien_id),
            ('annee', '=', annee),
            ('mois_num', '=', mois),
        ], limit=1)
        if not bordereau:
            MOIS_FR = {
                1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
                5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
                9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
            }
            bordereau = self.create({
                'praticien_id': praticien_id,
                'mois': f"{MOIS_FR[mois]} {annee}",
                'date_bordereau': datetime.date(annee, mois, 1),
            })
        return bordereau

    def action_validate(self):
        for rec in self:
            if not rec.feuille_ids:
                raise UserError(_('Impossible de valider un bordereau sans feuilles de soins.'))
            rec.feuille_ids.filtered(lambda f: f.state == 'confirmed').action_submit()
            rec.state = 'validated'

    def action_submit_cps(self):
        self.state = 'submitted'

    def action_close(self):
        self.state = 'closed'

    def action_reset_draft(self):
        self.state = 'draft'

    def action_print_bordereau(self):
        return self.env.ref('os_auxiliaire_medical.action_report_bordereau').report_action(self)

    def action_export_excel(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/cps/bordereau/{self.id}/xlsx',
            'target': 'new',
        }

    def get_lignes_for_report(self):
        lignes = []
        feuilles = self.feuille_ids.filtered(
            lambda f: f.state != 'cancelled'
        ).sorted('date_debut_soins')
        for i, feuille in enumerate(feuilles, start=1):
            lignes.append({
                'n': i,
                'nom_prenom': f"{feuille.patient_id.nom} {feuille.patient_id.prenom}",
                'dn': feuille.patient_id.dn or '',
                'date_debut': feuille.date_debut_soins.strftime('%d%m%y') if feuille.date_debut_soins else '',
                'date_fin': feuille.date_fin_soins.strftime('%d%m%y') if feuille.date_fin_soins else '',
                'montant_cps': feuille.montant_tiers_payant,
                'montant_patient': feuille.montant_patient,
                'montant_total': feuille.montant_total,
            })
        return lignes

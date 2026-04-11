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

    @api.depends('feuille_ids.montant_total', 'feuille_ids.montant_tiers_payant',
                 'feuille_ids.montant_patient')
    def _compute_totaux(self):
        for rec in self:
            rec.nb_feuilles = len(rec.feuille_ids)
            rec.total_cps = sum(rec.feuille_ids.mapped('montant_tiers_payant'))
            rec.total_patient = sum(rec.feuille_ids.mapped('montant_patient'))
            rec.total_general = rec.total_cps + rec.total_patient

    def action_validate(self):
        for rec in self:
            if not rec.feuille_ids:
                raise UserError(_('Impossible de valider un bordereau sans feuilles de soins.'))
            rec.feuille_ids.action_submit()
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
        """Retourne les lignes ordonnées pour le rapport."""
        lignes = []
        for i, feuille in enumerate(self.feuille_ids.sorted('date_debut_soins'), start=1):
            lignes.append({
                'n': i,
                'nom_prenom': f"{feuille.patient_id.nom} {feuille.patient_id.prenom}",
                'dn': feuille.patient_id.dn or '',
                'date_debut': feuille.date_debut_soins.strftime('%d/%m/%y') if feuille.date_debut_soins else '',
                'date_fin': feuille.date_fin_soins.strftime('%d/%m/%y') if feuille.date_fin_soins else '',
                'montant_cps': feuille.montant_tiers_payant,
                'montant_patient': feuille.montant_patient,
                'montant_total': feuille.montant_total,
            })
        return lignes

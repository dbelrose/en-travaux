import datetime
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CpsOrdonnance(models.Model):
    _name = 'cps.ordonnance'
    _description = 'Ordonnance médicale (prescription)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_prescription desc'

    name = fields.Char(required=True, copy=False,
                        default=lambda self: _('Nouvelle'), tracking=True)

    # Patient → res.partner catégorie Patient CPS
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        domain="[('category_id.name', '=', 'Patient CPS')]",
        ondelete='restrict', tracking=True,
    )

    # Praticien → res.partner catégorie Praticien CPS
    praticien_id = fields.Many2one(
        'res.partner', string='Praticien destinataire',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        ondelete='restrict',
        default=lambda self: self.env['res.partner'].search(
            [('user_ids', 'in', self.env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1,
        ),
    )
    # Profession : calculée depuis category_id du praticien (pas de champ sur res.partner)
    praticien_profession = fields.Char(
        compute='_compute_praticien_profession', store=False,
    )

    @api.depends('praticien_id', 'praticien_id.category_id',
                 'praticien_id.category_id.parent_id')
    def _compute_praticien_profession(self):
        for rec in self:
            rec.praticien_profession = rec.praticien_id.get_cps_profession_key() or '' if rec.praticien_id else ''

    # Prescripteur → res.partner catégorie Prescripteur
    # prescripteur_code correspond maintenant à prescripteur_id.vat
    prescripteur_id = fields.Many2one(
        'res.partner', string='Prescripteur',
        domain="[('category_id.name', '=', 'Prescripteur')]",
        ondelete='set null',
    )
    prescripteur_nom = fields.Char(
        string='Nom du prescripteur',
        compute='_compute_prescripteur_nom', store=True, readonly=False,
    )
    # prescripteur_code = vat du prescripteur (lecture seule, depuis le partenaire)
    prescripteur_code = fields.Char(
        string='Code prescripteur (AM/RPPS)',
        related='prescripteur_id.vat', readonly=True,
        help='Valeur du champ « N° TVA / Identifiant » du contact prescripteur.',
    )

    @api.depends('prescripteur_id.name')
    def _compute_prescripteur_nom(self):
        for rec in self:
            if rec.prescripteur_id and not rec.prescripteur_nom:
                rec.prescripteur_nom = rec.prescripteur_id.name

    @api.onchange('prescripteur_id')
    def _onchange_prescripteur_id(self):
        if self.prescripteur_id:
            self.prescripteur_nom = self.prescripteur_id.name

    date_prescription = fields.Date(required=True, default=fields.Date.today, tracking=True)

    # date_fin_validite = date_prescription + paramètre config (modifiable manuellement)
    date_fin_validite = fields.Date(
        string='Fin de validité',
        compute='_compute_date_fin_validite', store=True, readonly=False,
    )

    @api.depends('date_prescription')
    def _compute_date_fin_validite(self):
        IrParam = self.env['ir.config_parameter'].sudo()
        validite_jours = int(IrParam.get_param('cps.ordonnance.validite_jours', 90))
        for rec in self:
            if rec.date_prescription:
                rec.date_fin_validite = (
                    rec.date_prescription + datetime.timedelta(days=validite_jours)
                )
            else:
                rec.date_fin_validite = False

    condition = fields.Selection([
        ('maladie', 'Maladie (défaut)'), ('longue_maladie', 'Longue Maladie'),
        ('at_mp', 'AT/MP'), ('maternite', 'Maternité'),
        ('urgence', 'Urgence'), ('autre', 'Autres dérogations'),
    ], default='maladie')
    motif_derogation = fields.Char()
    accord_prealable = fields.Char()
    num_rsr    = fields.Char(string='N° RSR')
    num_panier = fields.Char(string='N° panier de soins')

    ligne_ids   = fields.One2many('cps.ordonnance.ligne', 'ordonnance_id')
    feuille_ids = fields.One2many('cps.feuille.soins', 'ordonnance_id')

    state = fields.Selection([
        ('active', 'Active'), ('epuisee', 'Épuisée'),
        ('expiree', 'Expirée'), ('annulee', 'Annulée'),
    ], default='active', tracking=True)

    nb_seances_prescrites = fields.Integer(compute='_compute_stats')
    nb_seances_effectuees = fields.Integer(compute='_compute_stats')
    nb_seances_restantes  = fields.Integer(compute='_compute_stats')

    company_id = fields.Many2one('res.company', required=True,
                                  default=lambda self: self.env.company, index=True)

    @api.depends('ligne_ids.nb_seances_prescrites', 'ligne_ids.nb_seances_effectuees')
    def _compute_stats(self):
        for rec in self:
            rec.nb_seances_prescrites = sum(rec.ligne_ids.mapped('nb_seances_prescrites'))
            rec.nb_seances_effectuees = sum(rec.ligne_ids.mapped('nb_seances_effectuees'))
            rec.nb_seances_restantes  = max(0, rec.nb_seances_prescrites - rec.nb_seances_effectuees)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouvelle')) == _('Nouvelle'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('cps.ordonnance') or _('Nouvelle')
                )
        return super().create(vals_list)

    @api.constrains('patient_id', 'ligne_ids')
    def _check_patient_for_lines(self):
        for rec in self:
            if rec.ligne_ids and not rec.patient_id:
                raise ValidationError(
                    _("Le patient est obligatoire pour ajouter des actes.")
                )

    @api.constrains('ligne_ids')
    def _check_unique_acte_type_per_ligne(self):
        for rec in self:
            acte_ids = [l.acte_type_id.id for l in rec.ligne_ids if l.acte_type_id]
            if len(acte_ids) != len(set(acte_ids)):
                raise ValidationError(
                    _("Chaque type d'acte ne peut être présent qu'une seule fois.")
                )

    def action_annuler(self):   self.state = 'annulee'
    def action_reactiver(self): self.state = 'active'

    def action_view_feuilles(self):
        return {'type': 'ir.actions.act_window', 'name': 'Feuilles de soins',
                'res_model': 'cps.feuille.soins', 'view_mode': 'list,form',
                'domain': [('ordonnance_id', '=', self.id)]}

    def action_open_ocr_wizard(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Importer par OCR'),
                'res_model': 'cps.wizard.ocr.ordonnance', 'view_mode': 'form',
                'target': 'new', 'context': {'default_ordonnance_id': self.id}}


class CpsOrdonnanceLigne(models.Model):
    _name  = 'cps.ordonnance.ligne'
    _description = "Ligne d'ordonnance"
    _order = 'sequence, id'

    ordonnance_id = fields.Many2one('cps.ordonnance', required=True, ondelete='cascade')
    sequence      = fields.Integer(default=10)
    acte_type_id  = fields.Many2one('cps.acte.type', required=True, ondelete='restrict')
    lettre_cle    = fields.Char(related='acte_type_id.lettre_cle', readonly=True)
    coefficient   = fields.Float(related='acte_type_id.coefficient_defaut', readonly=True, digits=(6, 2))
    duree_seance  = fields.Integer(related='acte_type_id.duree_seance', readonly=True)
    delai_min_jours = fields.Integer(related='acte_type_id.delai_min_jours', readonly=True)
    nb_seances_prescrites = fields.Integer(default=1, required=True)

    acte_ids = fields.One2many('cps.feuille.soins.acte', 'ordonnance_ligne_id')
    nb_seances_effectuees = fields.Integer(compute='_compute_effectuees')
    nb_seances_restantes  = fields.Integer(compute='_compute_effectuees')
    progress = fields.Float(compute='_compute_effectuees', digits=(5, 1))

    @api.depends('acte_ids.feuille_id.state', 'nb_seances_prescrites')
    def _compute_effectuees(self):
        for rec in self:
            effectuees = len(
                rec.acte_ids.filtered(lambda a: a.feuille_id.state not in ('cancelled', 'draft'))
            )
            rec.nb_seances_effectuees = effectuees
            rec.nb_seances_restantes  = max(0, rec.nb_seances_prescrites - effectuees)
            rec.progress = (effectuees / rec.nb_seances_prescrites * 100
                            if rec.nb_seances_prescrites else 0.0)

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id(self):
        if self.acte_type_id and self.acte_type_id.nb_seances_defaut:
            self.nb_seances_prescrites = self.acte_type_id.nb_seances_defaut

    def get_last_seance_date(self):
        self.ensure_one()
        dates = self.acte_ids.filtered(
            lambda a: a.feuille_id.state not in ('cancelled', 'draft') and a.date_acte
        ).mapped('date_acte')
        return max(dates) if dates else None

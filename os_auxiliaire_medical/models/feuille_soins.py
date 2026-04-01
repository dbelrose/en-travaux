from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class CpsFeuillesSoins(models.Model):
    _name = 'cps.feuille.soins'
    _description = 'Feuille de soins auxiliaire médical (FSA25)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_prescription desc, name'

    # ── Identification ──────────────────────────────────────────────────────
    name = fields.Char(string='N° Facture', required=True, copy=False,
                        default=lambda self: _('Nouveau'), tracking=True)
    fsa_numero = fields.Char(string='N° FSA25', help='Numéro imprimé sur le formulaire')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('submitted', 'Soumise CPS'),
        ('paid', 'Remboursée'),
        ('cancelled', 'Annulée'),
    ], string='État', default='draft', tracking=True, required=True)

    # ── Bénéficiaire ────────────────────────────────────────────────────────
    patient_id = fields.Many2one('cps.patient', string='Patient (bénéficiaire)', required=True,
                                  tracking=True, ondelete='restrict')
    patient_nom = fields.Char(related='patient_id.nom', string='Nom', readonly=True)
    patient_prenom = fields.Char(related='patient_id.prenom', string='Prénom', readonly=True)
    patient_dn = fields.Char(related='patient_id.dn', string='DN', readonly=True)

    # ── Praticien ───────────────────────────────────────────────────────────
    praticien_id = fields.Many2one('cps.praticien', string='Auxiliaire médical', required=True,
                                    tracking=True, ondelete='restrict')
    code_auxiliaire = fields.Char(related='praticien_id.code_auxiliaire', readonly=True)
    auxiliaire_remplacant = fields.Boolean(string='Auxiliaire remplaçant')
    accord_prealable = fields.Char(string='Accord préalable n°')

    # ── Prescription ────────────────────────────────────────────────────────
    parcours_soins = fields.Boolean(string='Parcours de soins', default=False)
    code_prescripteur = fields.Char(string='Code prescripteur')
    date_prescription = fields.Date(string='Date de prescription', required=True)
    annee_prescription = fields.Integer(string='Année', compute='_compute_periode', store=True)
    mois_prescription = fields.Integer(string='Mois', compute='_compute_periode', store=True)

    # ── Condition de prise en charge ────────────────────────────────────────
    condition = fields.Selection([
        ('maladie', 'Maladie (défaut)'),
        ('longue_maladie', 'Longue Maladie'),
        ('at_mp', 'AT/MP'),
        ('maternite', 'Maternité'),
        ('urgence', 'Urgence'),
        ('autre', 'Autres dérogations'),
    ], string='Condition de prise en charge', default='maladie')
    num_rsr = fields.Char(string='N° RSR')
    num_panier = fields.Char(string='N° panier de soins')

    # ── Actes ────────────────────────────────────────────────────────────────
    acte_ids = fields.One2many('cps.feuille.soins.acte', 'feuille_id', string='Actes')

    # ── Montants calculés ───────────────────────────────────────────────────
    montant_total = fields.Float(string='Montant total', compute='_compute_montants', store=True)
    montant_tiers_payant = fields.Float(string='Montant tiers payant (CPS)',
                                         compute='_compute_montants', store=True)
    montant_patient = fields.Float(string='Montant payé par l\'assuré',
                                    compute='_compute_montants', store=True)
    taux_remboursement = fields.Float(string='Taux de remboursement (%)', default=70.0)

    # ── Bordereau ───────────────────────────────────────────────────────────
    bordereau_id = fields.Many2one('cps.bordereau', string='Bordereau', readonly=True,
                                    tracking=True)
    date_debut_soins = fields.Date(string='Date début des soins', compute='_compute_dates_soins',
                                    store=True)
    date_fin_soins = fields.Date(string='Date fin des soins', compute='_compute_dates_soins',
                                  store=True)

    # ── Photo / scan ────────────────────────────────────────────────────────
    photo_feuille = fields.Binary(string='Photo / scan de la feuille')
    photo_filename = fields.Char(string='Nom du fichier')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = self.env['ir.sequence'].next_by_code('cps.feuille.soins') or _('Nouveau')
        return super().create(vals_list)

    @api.depends('acte_ids.montant')
    def _compute_montants(self):
        for rec in self:
            total = sum(rec.acte_ids.mapped('montant'))
            rec.montant_total = total
            rec.montant_tiers_payant = round(total * rec.taux_remboursement / 100, 0)
            rec.montant_patient = round(total - rec.montant_tiers_payant, 0)

    @api.depends('acte_ids.date_acte')
    def _compute_dates_soins(self):
        for rec in self:
            dates = rec.acte_ids.mapped('date_acte')
            dates = [d for d in dates if d]
            rec.date_debut_soins = min(dates) if dates else False
            rec.date_fin_soins = max(dates) if dates else False

    @api.depends('date_prescription')
    def _compute_periode(self):
        for rec in self:
            if rec.date_prescription:
                rec.annee_prescription = rec.date_prescription.year
                rec.mois_prescription = rec.date_prescription.month
            else:
                rec.annee_prescription = 0
                rec.mois_prescription = 0

    def action_confirm(self):
        for rec in self:
            if rec.praticien_id and rec.date_prescription and not rec.bordereau_id:
                bordereau = self.env['cps.bordereau']._get_or_create_bordereau(
                    praticien_id=rec.praticien_id.id,
                    annee=rec.date_prescription.year,
                    mois=rec.date_prescription.month,
                )
                rec.bordereau_id = bordereau.id
        self.write({'state': 'confirmed'})

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_paid(self):
        self.write({'state': 'paid'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_print_feuille(self):
        return self.env.ref('os_auxiliaire_medical.action_report_feuille_soins').report_action(self)


class CpsActe(models.Model):
    _name = 'cps.feuille.soins.acte'
    _description = 'Acte de soin (ligne de feuille FSA25)'
    _order = 'date_acte'

    feuille_id = fields.Many2one('cps.feuille.soins', string='Feuille de soins',
                                  required=True, ondelete='cascade')
    date_acte = fields.Date(string='Date', required=True)
    lettre_cle = fields.Char(string='Lettre clé', size=10, help='Ex: AMO, AMK, AMS...')
    coefficient = fields.Float(string='Coefficient', digits=(6, 2))

    # Frais de déplacement
    ifd = fields.Float(string='IFD', default=0)
    ik = fields.Float(string='IK', default=0)

    # Majoration
    dimanche_ferie = fields.Boolean(string='Dimanche / J. Férie')
    nuit = fields.Boolean(string='Nuit')
    taux_majoration = fields.Float(string='Taux majoration (%)', default=0)

    montant = fields.Float(string='Montant', required=True, digits=(10, 0))

    @api.onchange('lettre_cle', 'coefficient')
    def _onchange_compute_hint(self):
        # Valeur unitaire indicative AMO = ~433 F (ajustable via config)
        tarifs = {'AMO': 433, 'AMK': 433, 'AMS': 283, 'AMI': 366}
        if self.lettre_cle and self.coefficient:
            base = tarifs.get(self.lettre_cle.upper(), 433)
            self.montant = round(base * self.coefficient, 0)

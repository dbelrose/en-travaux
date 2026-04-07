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
    montant_patient = fields.Float(string="Montant payé par l'assuré",
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

    # ── Champs texte pour formulaire PDF ────────────────────────────────────

    # Selection
    state_texte = fields.Char(string='État (texte)', compute='_compute_champs_texte', store=True)

    # Informations facultatives
    num_rsr_texte = fields.Char(string='N° RSR texte', compute='_compute_champs_texte', store=True)
    num_panier_texte = fields.Char(string='N° panier de soins texte', compute='_compute_champs_texte', store=True)

    # Booléens
    auxiliaire_remplacant_oui = fields.Char(string='Remplaçant Oui', compute='_compute_champs_texte', store=True)
    auxiliaire_remplacant_non = fields.Char(string='Remplaçant Non', compute='_compute_champs_texte', store=True)
    parcours_soins_oui = fields.Char(string='Parcours de soins Oui', compute='_compute_champs_texte', store=True)
    at_mp_oui = fields.Char(string='AT/MP Oui', compute='_compute_champs_texte', store=True)
    autre_oui = fields.Char(string='AT/MP Oui', compute='_compute_champs_texte', store=True)
    maladie_oui = fields.Char(string='AT/MP Oui', compute='_compute_champs_texte', store=True)
    longue_maladie_oui = fields.Char(string='Longue maladie Oui', compute='_compute_champs_texte', store=True)
    maternite_oui = fields.Char(string='Maternité Oui', compute='_compute_champs_texte', store=True)
    urgence_oui = fields.Char(string='Urgence Oui', compute='_compute_champs_texte', store=True)

    # Dates
    date_prescription_texte = fields.Char(string='Date prescription (texte)', compute='_compute_champs_texte', store=True)
    date_debut_soins_texte = fields.Char(string='Date début soins (texte)', compute='_compute_champs_texte', store=True)
    date_fin_soins_texte = fields.Char(string='Date fin soins (texte)', compute='_compute_champs_texte', store=True)

    # Montants
    montant_total_texte = fields.Char(string='Montant total (texte)', compute='_compute_champs_texte', store=True)
    montant_tiers_payant_texte = fields.Char(string='Montant tiers payant (texte)', compute='_compute_champs_texte', store=True)
    montant_patient_texte = fields.Char(string='Montant patient (texte)', compute='_compute_champs_texte', store=True)
    taux_remboursement_texte = fields.Char(string='Taux remboursement (texte)', compute='_compute_champs_texte', store=True)

    # Patient
    patient_nom_texte = fields.Char(string='Patient nom', compute='_compute_champs_texte', store=True)
    patient_prenom_texte = fields.Char(string='Patient prénom', compute='_compute_champs_texte', store=True)
    patient_dn_texte = fields.Char(string='Patient DN', compute='_compute_champs_texte', store=True)
    patient_date_naissance_texte = fields.Char(string='Patient date naissance', compute='_compute_champs_texte', store=True)
    patient_assure_nom_texte = fields.Char(string='Assuré nom', compute='_compute_champs_texte', store=True)
    patient_assure_prenom_texte = fields.Char(string='Assuré prénom', compute='_compute_champs_texte', store=True)
    patient_assure_dn_texte = fields.Char(string='Assuré DN', compute='_compute_champs_texte', store=True)

    # Praticien
    praticien_name_texte = fields.Char(string='Praticien nom', compute='_compute_champs_texte', store=True)
    praticien_code_texte = fields.Char(string='Praticien code auxiliaire', compute='_compute_champs_texte', store=True)
    praticien_profession_texte = fields.Char(string='Praticien profession', compute='_compute_champs_texte', store=True)
    praticien_bp_texte = fields.Char(string='Praticien BP/Adresse', compute='_compute_champs_texte', store=True)
    praticien_tel_texte = fields.Char(string='Praticien téléphone', compute='_compute_champs_texte', store=True)

    # Bordereau
    bordereau_name_texte = fields.Char(string='N° Bordereau', compute='_compute_champs_texte', store=True)

    # Acte 1
    acte_01_date_texte = fields.Char(string='Acte 1 date', compute='_compute_champs_texte', store=True)
    acte_01_lettre_cle_texte = fields.Char(string='Acte 1 lettre clé', compute='_compute_champs_texte', store=True)
    acte_01_coefficient_texte = fields.Char(string='Acte 1 coefficient', compute='_compute_champs_texte', store=True)
    acte_01_ifd_texte = fields.Char(string='Acte 1 IFD', compute='_compute_champs_texte', store=True)
    acte_01_ik_texte = fields.Char(string='Acte 1 IK', compute='_compute_champs_texte', store=True)
    acte_01_taux_majoration_texte = fields.Char(string='Acte 1 taux majoration', compute='_compute_champs_texte', store=True)
    acte_01_montant_texte = fields.Char(string='Acte 1 montant', compute='_compute_champs_texte', store=True)
    acte_01_dimanche_ferie_oui = fields.Char(string='Acte 1 dimanche/férié Oui', compute='_compute_champs_texte', store=True)
    acte_01_dimanche_ferie_non = fields.Char(string='Acte 1 dimanche/férié Non', compute='_compute_champs_texte', store=True)
    acte_01_nuit_oui = fields.Char(string='Acte 1 nuit Oui', compute='_compute_champs_texte', store=True)
    acte_01_nuit_non = fields.Char(string='Acte 1 nuit Non', compute='_compute_champs_texte', store=True)

    # Acte 2
    acte_02_date_texte = fields.Char(string='Acte 2 date', compute='_compute_champs_texte', store=True)
    acte_02_lettre_cle_texte = fields.Char(string='Acte 2 lettre clé', compute='_compute_champs_texte', store=True)
    acte_02_coefficient_texte = fields.Char(string='Acte 2 coefficient', compute='_compute_champs_texte', store=True)
    acte_02_ifd_texte = fields.Char(string='Acte 2 IFD', compute='_compute_champs_texte', store=True)
    acte_02_ik_texte = fields.Char(string='Acte 2 IK', compute='_compute_champs_texte', store=True)
    acte_02_taux_majoration_texte = fields.Char(string='Acte 2 taux majoration', compute='_compute_champs_texte', store=True)
    acte_02_montant_texte = fields.Char(string='Acte 2 montant', compute='_compute_champs_texte', store=True)
    acte_02_dimanche_ferie_oui = fields.Char(string='Acte 2 dimanche/férié Oui', compute='_compute_champs_texte', store=True)
    acte_02_dimanche_ferie_non = fields.Char(string='Acte 2 dimanche/férié Non', compute='_compute_champs_texte', store=True)
    acte_02_nuit_oui = fields.Char(string='Acte 2 nuit Oui', compute='_compute_champs_texte', store=True)
    acte_02_nuit_non = fields.Char(string='Acte 2 nuit Non', compute='_compute_champs_texte', store=True)

    @api.depends(
        'state', 'condition', 'num_rsr', 'num_panier',
        'auxiliaire_remplacant', 'parcours_soins',
        'date_prescription', 'date_debut_soins', 'date_fin_soins',
        'montant_total', 'montant_tiers_payant', 'montant_patient', 'taux_remboursement',
        'patient_id.nom', 'patient_id.prenom', 'patient_id.dn', 'patient_id.date_naissance',
        'patient_id.assure_nom', 'patient_id.assure_prenom', 'patient_id.assure_dn',
        'praticien_id.name', 'praticien_id.code_auxiliaire', 'praticien_id.profession',
        'praticien_id.bp', 'praticien_id.tel',
        'bordereau_id.name',
        'acte_ids.date_acte', 'acte_ids.lettre_cle', 'acte_ids.coefficient',
        'acte_ids.ifd', 'acte_ids.ik', 'acte_ids.taux_majoration', 'acte_ids.montant',
        'acte_ids.dimanche_ferie', 'acte_ids.nuit',
    )
    def _compute_champs_texte(self):

        def fmt_date(d):
            return d.strftime('%d%m%y') if d else ''

        def fmt_date_8(d):
            return d.strftime('%d%m%Y') if d else ''

        def fmt_float(v):
            return '{:,.0f}'.format(v).replace(',', ' ') if v else '0'

        state_labels = dict(self._fields['state'].selection)
        condition_labels = dict(self._fields['condition'].selection)
        profession_labels = dict(self.env['cps.praticien']._fields['profession'].selection)

        for rec in self:
            rec.state_texte = state_labels.get(rec.state, rec.state or '')

            rec.auxiliaire_remplacant_oui = 'x' if rec.auxiliaire_remplacant else ''
            rec.auxiliaire_remplacant_non = '' if rec.auxiliaire_remplacant else 'x'
            rec.parcours_soins_oui = 'x' if rec.parcours_soins else ''
            rec.maternite_oui = 'x' if rec.condition == 'maternite' else ''
            rec.urgence_oui = 'x' if rec.condition == 'urgence' else ''
            rec.longue_maladie_oui = 'x' if rec.condition == 'longue_maladie' else ''
            rec.maladie_oui = 'x' if rec.condition == 'maladie' else ''
            rec.at_mp_oui = 'x' if rec.condition == 'at_mp' else ''
            rec.autre_oui = 'x' if rec.condition == 'autre' else ''
            rec.num_panier_texte = rec.num_panier or ''
            rec.num_rsr_texte = rec.num_rsr or ''

            rec.date_prescription_texte = fmt_date(rec.date_prescription)
            rec.date_debut_soins_texte = fmt_date(rec.date_debut_soins)
            rec.date_fin_soins_texte = fmt_date(rec.date_fin_soins)

            rec.montant_total_texte = fmt_float(rec.montant_total)
            rec.montant_tiers_payant_texte = fmt_float(rec.montant_tiers_payant)
            rec.montant_patient_texte = fmt_float(rec.montant_patient)
            rec.taux_remboursement_texte = '{:g}'.format(rec.taux_remboursement)

            p = rec.patient_id
            rec.patient_nom_texte = (p.nom.upper() or '') if p else ''
            rec.patient_prenom_texte = (rec.patient_prenom.upper() or '') if p else ''
            rec.patient_dn_texte = (p.dn.upper() or '') if p else ''
            rec.patient_date_naissance_texte = fmt_date_8(p.date_naissance) if p else ''
            rec.patient_assure_nom_texte = ((p.assure_nom or '') if p else '').upper()
            rec.patient_assure_prenom_texte = ((p.assure_prenom or '') if p else '').upper()
            rec.patient_assure_dn_texte = (p.assure_dn or '') if p else ''

            pr = rec.praticien_id
            rec.praticien_name_texte = ((pr.name or '') if pr else '').upper()
            rec.praticien_code_texte = ((pr.code_auxiliaire or '') if pr else '').upper()
            rec.praticien_profession_texte = profession_labels.get(pr.profession, pr.profession or '') if pr else ''
            rec.praticien_bp_texte = (pr.bp or '') if pr else ''
            rec.praticien_tel_texte = (pr.tel or '') if pr else ''

            rec.bordereau_name_texte = (rec.bordereau_id.name or '') if rec.bordereau_id else ''

            a1 = rec.acte_ids[0] if len(rec.acte_ids) >= 1 else None
            rec.acte_01_date_texte = fmt_date(a1.date_acte) if a1 else ''
            rec.acte_01_lettre_cle_texte = (a1.lettre_cle or '') if a1 else ''
            rec.acte_01_coefficient_texte = '{:g}'.format(a1.coefficient) if a1 and a1.coefficient else ''
            rec.acte_01_ifd_texte = fmt_float(a1.ifd) if a1 and a1.ifd else ''
            rec.acte_01_ik_texte = fmt_float(a1.ik) if a1 and a1.ik else ''
            rec.acte_01_taux_majoration_texte = '{:g}'.format(a1.taux_majoration) if a1 and a1.taux_majoration else ''
            rec.acte_01_montant_texte = fmt_float(a1.montant) if a1 else ''
            rec.acte_01_dimanche_ferie_oui = ('x' if a1.dimanche_ferie else '') if a1 else ''
            rec.acte_01_dimanche_ferie_non = ('' if a1.dimanche_ferie else 'x') if a1 else ''
            rec.acte_01_nuit_oui = ('x' if a1.nuit else '') if a1 else ''
            rec.acte_01_nuit_non = ('' if a1.nuit else 'x') if a1 else ''

            a2 = rec.acte_ids[1] if len(rec.acte_ids) >= 2 else None
            rec.acte_02_date_texte = fmt_date(a2.date_acte) if a2 else ''
            rec.acte_02_lettre_cle_texte = (a2.lettre_cle or '') if a2 else ''
            rec.acte_02_coefficient_texte = '{:g}'.format(a2.coefficient) if a2 and a2.coefficient else ''
            rec.acte_02_ifd_texte = fmt_float(a2.ifd) if a2 and a2.ifd else ''
            rec.acte_02_ik_texte = fmt_float(a2.ik) if a2 and a2.ik else ''
            rec.acte_02_taux_majoration_texte = '{:g}'.format(a2.taux_majoration) if a2 and a2.taux_majoration else ''
            rec.acte_02_montant_texte = fmt_float(a2.montant) if a2 else ''
            rec.acte_02_dimanche_ferie_oui = ('x' if a2.dimanche_ferie else '') if a2 else ''
            rec.acte_02_dimanche_ferie_non = ('' if a2.dimanche_ferie else 'x') if a2 else ''
            rec.acte_02_nuit_oui = ('x' if a2.nuit else '') if a2 else ''
            rec.acte_02_nuit_non = ('' if a2.nuit else 'x') if a2 else ''

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

    def action_confirm(self):
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

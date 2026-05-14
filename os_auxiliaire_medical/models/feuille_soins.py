from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz
from datetime import datetime as dt

PROFESSION_LABELS = {
    'kinesitherapeute': 'Masseur-kinésithérapeute',
    'orthophoniste': 'Orthophoniste',
    'orthoptiste': 'Orthoptiste',
    'pedicure': 'Pédicure-Podologue',
    'infirmier': 'Infirmier(e)',
    'autre': 'Autre',
}
PRATICIEN_CPS_CAT = 'Praticien CPS'
_TZ_TAHITI = 'Pacific/Tahiti'


def _default_praticien(env):
    return env['res.partner'].search(
        [('user_id', '=', env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1,
    )


def _profession_from_partner(partner):
    if not partner:
        return False
    return partner.get_cps_profession_key()


class CpsFeuillesSoins(models.Model):
    _name = 'cps.feuille.soins'
    _description = 'Feuille de soins auxiliaire médical (FSA25)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_prescription desc, name'

    fsa_numero = fields.Char(string='N° FSA25', copy=False, readonly=True)
    name = fields.Char(string='N° Facture', required=True, copy=False,
                       default=lambda self: _('Nouveau'), tracking=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Brouillon'), ('confirmed', 'Confirmée'),
        ('submitted', 'Soumise CPS'), ('paid', 'Remboursée'), ('cancelled', 'Annulée'),
    ], default='draft', tracking=True, required=True)

    ordonnance_id = fields.Many2one(
        'cps.ordonnance', string='Ordonnance',
        domain="[('state', 'in', ['en_cours', 'brouillon']), ('has_seances_disponibles', '=', True)]",
        ondelete='set null', tracking=True,
    )

    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        tracking=True, ondelete='restrict',
        compute='_compute_patient_id', store=True, readonly=False,
    )
    patient_nom = fields.Char(related='patient_id.lastname', readonly=True)
    patient_prenom = fields.Char(related='patient_id.firstname', readonly=True)
    patient_dn = fields.Char(related='patient_id.vat', readonly=True, string='DN')

    @api.depends('ordonnance_id.patient_id')
    def _compute_patient_id(self):
        for rec in self:
            if rec.ordonnance_id and rec.ordonnance_id.patient_id:
                rec.patient_id = rec.ordonnance_id.patient_id

    @api.constrains('patient_id')
    def _check_patient_id(self):
        for rec in self:
            if not rec.patient_id:
                raise UserError(_('Le patient est obligatoire.'))

    praticien_id = fields.Many2one(
        'res.partner', string='Auxiliaire médical',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        tracking=True, ondelete='restrict',
        compute='_compute_praticien_id', store=True, readonly=False,
    )
    praticien_profession = fields.Char(
        compute='_compute_praticien_profession', string='Profession praticien', store=False,
    )
    code_auxiliaire = fields.Char(related='praticien_id.vat', readonly=True, string='Code auxiliaire')
    auxiliaire_remplacant = fields.Boolean(string='Auxiliaire remplaçant')
    accord_prealable = fields.Char(string='Accord préalable n°')
    modele_id = fields.Many2one('cps.feuille.soins.modele', string='Appliquer un modèle')

    @api.depends('ordonnance_id.praticien_id')
    def _compute_praticien_id(self):
        default_praticien = self.env['res.partner'].search(
            [('user_ids', 'in', self.env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1,
        )
        for rec in self:
            if rec.ordonnance_id and rec.ordonnance_id.praticien_id:
                rec.praticien_id = rec.ordonnance_id.praticien_id
            elif not rec.praticien_id:
                rec.praticien_id = default_praticien

    @api.constrains('praticien_id')
    def _check_praticien_id(self):
        for rec in self:
            if not rec.praticien_id:
                raise UserError(_('Le praticien est obligatoire.'))

    @api.depends('praticien_id', 'praticien_id.category_id', 'praticien_id.category_id.parent_id')
    def _compute_praticien_profession(self):
        for rec in self:
            rec.praticien_profession = _profession_from_partner(rec.praticien_id) or ''

    parcours_soins = fields.Boolean(default=False)
    code_prescripteur = fields.Char(string='Code prescripteur')
    date_prescription = fields.Date(string='Date de prescription', required=True)
    condition = fields.Selection([
        ('maladie', 'Maladie (défaut)'), ('longue_maladie', 'Longue Maladie'),
        ('at_mp', 'AT/MP'), ('maternite', 'Maternité'),
        ('urgence', 'Urgence'), ('autre', 'Autres dérogations'),
    ], default='maladie')
    motif_derogation = fields.Char(string='Motif de dérogation')
    num_rsr = fields.Char(string='N° RSR')
    num_panier = fields.Char(string='N° panier de soins')

    acte_ids = fields.One2many('cps.feuille.soins.acte', 'feuille_id', string='Actes')
    montant_total = fields.Float(compute='_compute_montants', store=True)
    montant_tiers_payant = fields.Float(compute='_compute_montants', store=True)
    montant_patient = fields.Float(compute='_compute_montants', store=True)
    taux_remboursement = fields.Float(string='Taux de remboursement (%)', default=70.0)

    bordereau_id = fields.Many2one('cps.bordereau', readonly=True, tracking=True)
    date_debut_soins = fields.Date(compute='_compute_dates_soins', store=True)
    date_fin_soins = fields.Date(compute='_compute_dates_soins', store=True)

    # ── Date de la feuille ────────────────────────────────────────────────────
    # Initialisée à max(today, date de la dernière séance).
    # Modifiable manuellement si besoin.
    date_feuille = fields.Date(
        string='Date de la feuille',
        compute='_compute_date_feuille',
        store=True,
        readonly=False,
        tracking=True,
        help='Date du formulaire FSA25 : au maximum entre la date du jour '
             'et la date de la dernière séance. Modifiable manuellement.',
    )

    @api.depends('date_fin_soins')
    def _compute_date_feuille(self):
        today = fields.Date.today()
        for rec in self:
            if rec.date_fin_soins:
                rec.date_feuille = max(today, rec.date_fin_soins)
            elif not rec.date_feuille:
                rec.date_feuille = today

    # ── Mutuelle ─────────────────────────────────────────────────────────────
    has_mutuelle = fields.Boolean(
        string='Mutuelle',
        compute='_compute_has_mutuelle',
        store=False,
        help="Coché si le patient dispose d'une mutuelle complémentaire.",
    )

    @api.depends('patient_id')
    def _compute_has_mutuelle(self):
        patient_ids = self.mapped('patient_id').ids
        configs = self.env['cps.patient.config'].search(
            [('partner_id', 'in', patient_ids)]
        )
        config_map = {c.partner_id.id: c.has_mutuelle for c in configs}
        for rec in self:
            rec.has_mutuelle = config_map.get(rec.patient_id.id, False) if rec.patient_id else False

    # ── Indicateur séances futures ────────────────────────────────────────────
    has_future_seances = fields.Boolean(
        compute='_compute_has_future_seances',
        store=True,
        string='Séances futures',
        help='Vrai si la feuille contient au moins une séance planifiée dans le futur.',
    )

    @api.depends('acte_ids.date_acte', 'acte_ids.state_seance')
    def _compute_has_future_seances(self):
        today = fields.Date.today()
        for rec in self:
            rec.has_future_seances = any(
                a.date_acte and a.date_acte > today
                for a in rec.acte_ids
            )

    photo_feuille = fields.Binary(string='Photo / scan')
    photo_filename = fields.Char()
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company, index=True)

    # ── Champs texte PDF ──────────────────────────────────────────────────────
    state_texte = fields.Char(compute='_compute_champs_texte', store=True)
    num_rsr_texte = fields.Char(compute='_compute_champs_texte', store=True)
    num_panier_texte = fields.Char(compute='_compute_champs_texte', store=True)
    motif_derogation_texte = fields.Char(compute='_compute_champs_texte', store=True)
    auxiliaire_remplacant_oui = fields.Char(compute='_compute_champs_texte', store=True)
    auxiliaire_remplacant_non = fields.Char(compute='_compute_champs_texte', store=True)
    parcours_soins_oui = fields.Char(compute='_compute_champs_texte', store=True)
    at_mp_oui = fields.Char(compute='_compute_champs_texte', store=True)
    autre_oui = fields.Char(compute='_compute_champs_texte', store=True)
    maladie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    longue_maladie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    maternite_oui = fields.Char(compute='_compute_champs_texte', store=True)
    urgence_oui = fields.Char(compute='_compute_champs_texte', store=True)
    date_prescription_texte = fields.Char(compute='_compute_champs_texte', store=True)
    date_debut_soins_texte = fields.Char(compute='_compute_champs_texte', store=True)
    date_fin_soins_texte = fields.Char(compute='_compute_champs_texte', store=True)
    montant_total_texte = fields.Char(compute='_compute_champs_texte', store=True)
    montant_tiers_payant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    montant_patient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    taux_remboursement_texte = fields.Char(compute='_compute_champs_texte', store=True)
    patient_nom_texte = fields.Char(compute='_compute_champs_texte', store=True)
    patient_prenom_texte = fields.Char(compute='_compute_champs_texte', store=True)
    patient_dn_texte = fields.Char(compute='_compute_champs_texte', store=True)
    patient_date_naissance_texte = fields.Char(compute='_compute_champs_texte', store=True)
    praticien_name_texte = fields.Char(compute='_compute_champs_texte', store=True)
    praticien_code_texte = fields.Char(compute='_compute_champs_texte', store=True)
    praticien_profession_texte = fields.Char(compute='_compute_champs_texte', store=True)
    praticien_bp_texte = fields.Char(compute='_compute_champs_texte', store=True)
    praticien_tel_texte = fields.Char(compute='_compute_champs_texte', store=True)
    bordereau_name_texte = fields.Char(compute='_compute_champs_texte', store=True)

    acte_01_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_01_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_02_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_02_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_03_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_03_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_04_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_04_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_05_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_05_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_06_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_06_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_07_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_07_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_08_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_08_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_09_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_09_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_10_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_10_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_11_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_11_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_12_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_12_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_13_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_13_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_14_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_14_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_15_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_15_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    acte_16_date_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_lettre_cle_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_coefficient_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_ifd_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_ik_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_taux_majoration_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_montant_texte = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_dimanche_ferie_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_dimanche_ferie_non = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_nuit_oui = fields.Char(compute='_compute_champs_texte', store=True)
    acte_16_nuit_non = fields.Char(compute='_compute_champs_texte', store=True)

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('ordonnance_id')
    def _onchange_ordonnance_id(self):
        if not self.ordonnance_id:
            return
        self.parcours_soins = True
        o = self.ordonnance_id
        self.patient_id = o.patient_id
        if o.praticien_id:
            self.praticien_id = o.praticien_id
        self.date_prescription = o.date_prescription
        self.code_prescripteur = o.prescripteur_id.vat if o.prescripteur_id else ''

    @api.onchange('modele_id')
    def _onchange_modele_id(self):
        if not self.modele_id:
            return
        m = self.modele_id
        self.condition = m.condition
        self.taux_remboursement = m.taux_remboursement
        today = fields.Date.today()
        IrParam = self.env['ir.config_parameter'].sudo()
        ifd_sup = float(IrParam.get_param('cps.supplement.ifd', 250))
        lignes = []
        for ligne in m.ligne_ids:
            at = ligne.acte_type_id
            coef = ligne.coefficient or at.coefficient_defaut
            tarif = self._get_tarif_unitaire(at, IrParam)
            montant = round(tarif * coef, 0) if tarif else 0.0
            if ligne.ifd:
                montant += round(ligne.ifd * ifd_sup, 0)
            lignes.append((0, 0, {
                'acte_type_id': at.id, 'date_acte': today,
                'lettre_cle': at.lettre_cle, 'coefficient': coef,
                'ifd': ligne.ifd, 'ik': ligne.ik,
                'dimanche_ferie': ligne.dimanche_ferie, 'nuit': ligne.nuit,
                'montant': montant,
            }))
        self.acte_ids = [(5, 0, 0)] + lignes

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends(
        'state', 'condition', 'motif_derogation', 'num_rsr', 'num_panier',
        'auxiliaire_remplacant', 'parcours_soins',
        'date_prescription', 'date_debut_soins', 'date_fin_soins',
        'montant_total', 'montant_tiers_payant', 'montant_patient', 'taux_remboursement',
        'patient_id.lastname', 'patient_id.firstname', 'patient_id.vat',
        'patient_id.birthdate_date',
        'praticien_id.name', 'praticien_id.vat',
        'praticien_id.category_id', 'praticien_id.category_id.parent_id',
        'praticien_id.street', 'praticien_id.phone',
        'bordereau_id.name',
        'acte_ids.date_acte', 'acte_ids.lettre_cle', 'acte_ids.coefficient',
        'acte_ids.ifd', 'acte_ids.ik', 'acte_ids.taux_majoration', 'acte_ids.montant',
        'acte_ids.dimanche_ferie', 'acte_ids.nuit',
    )
    def _compute_champs_texte(self):
        def fd(d):
            return d.strftime('%d%m%y') if d else ''

        def fd8(d):
            return d.strftime('%d%m%Y') if d else ''

        def ff(v):
            return '{:,.0f}'.format(v).replace(',', ' ') if v else '0'

        sl = dict(self._fields['state'].selection)
        for rec in self:
            rec.state_texte = sl.get(rec.state, rec.state or '')
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
            rec.motif_derogation_texte = rec.motif_derogation or ''
            rec.date_prescription_texte = fd(rec.date_prescription)
            rec.date_debut_soins_texte = fd(rec.date_debut_soins)
            rec.date_fin_soins_texte = fd(rec.date_fin_soins)
            rec.montant_total_texte = ff(rec.montant_total)
            rec.montant_tiers_payant_texte = ff(rec.montant_tiers_payant)
            rec.montant_patient_texte = ff(rec.montant_patient)
            rec.taux_remboursement_texte = '{:g}'.format(rec.taux_remboursement)
            p = rec.patient_id
            rec.patient_nom_texte = (p.lastname.upper() if p and p.lastname else '')
            rec.patient_prenom_texte = (p.firstname.upper() if p and p.firstname else '')
            rec.patient_dn_texte = (p.vat.upper() if p and p.vat else '')
            rec.patient_date_naissance_texte = fd8(p.birthdate_date) if p else ''
            pr = rec.praticien_id
            rec.praticien_name_texte = (pr.name or '').upper() if pr else ''
            rec.praticien_code_texte = (pr.vat or '').upper() if pr else ''
            rec.praticien_profession_texte = pr.get_cps_profession_label() if pr else ''
            rec.praticien_bp_texte = (pr.street or '') if pr else ''
            rec.praticien_tel_texte = (pr.phone or '') if pr else ''
            rec.bordereau_name_texte = (rec.bordereau_id.name or '') if rec.bordereau_id else ''

            for i in range(1, 17):
                idx = i - 1
                acte = rec.acte_ids[idx] if len(rec.acte_ids) > idx else None
                suffix = f'{i:02d}'
                setattr(rec, f'acte_{suffix}_date_texte',
                        fd(acte.date_acte) if acte else '')
                setattr(rec, f'acte_{suffix}_lettre_cle_texte',
                        (acte.lettre_cle or '') if acte else '')
                setattr(rec, f'acte_{suffix}_coefficient_texte',
                        '{:g}'.format(acte.coefficient) if acte and acte.coefficient else '')
                setattr(rec, f'acte_{suffix}_ifd_texte',
                        ff(acte.ifd) if acte and acte.ifd else '')
                setattr(rec, f'acte_{suffix}_ik_texte',
                        ff(acte.ik) if acte and acte.ik else '')
                setattr(rec, f'acte_{suffix}_taux_majoration_texte',
                        '{:g}'.format(acte.taux_majoration) if acte and acte.taux_majoration else '')
                setattr(rec, f'acte_{suffix}_montant_texte',
                        ff(acte.montant) if acte else '')
                setattr(rec, f'acte_{suffix}_dimanche_ferie_oui',
                        'x' if acte and acte.dimanche_ferie else '')
                setattr(rec, f'acte_{suffix}_dimanche_ferie_non',
                        '' if acte and acte.dimanche_ferie else 'x' if acte else '')
                setattr(rec, f'acte_{suffix}_nuit_oui',
                        'x' if acte and acte.nuit else '')
                setattr(rec, f'acte_{suffix}_nuit_non',
                        '' if acte and acte.nuit else 'x' if acte else '')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('fsa_numero'):
                vals['fsa_numero'] = (
                        self.env['ir.sequence'].next_by_code('cps.feuille.soins.fsa') or '000001'
                )
            if vals.get('name', _('Nouveau')) == _('Nouveau'):
                vals['name'] = 'FSA25-{}'.format(vals['fsa_numero'])
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
            dates = [d for d in rec.acte_ids.mapped('date_acte') if d]
            rec.date_debut_soins = min(dates) if dates else False
            rec.date_fin_soins = max(dates) if dates else False

    @staticmethod
    def _get_tarif_unitaire(acte_type, ir_param):
        cfg = {
            'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
            'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI': 'cps.tarif.ami',
            'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams',
        }
        lk = (acte_type.lettre_cle or '').upper()
        key = cfg.get(lk)
        return float(ir_param.get_param(key, acte_type.tarif_unitaire or 490)) if key else (
                    acte_type.tarif_unitaire or 490)

    # ── Actions workflow ──────────────────────────────────────────────────────

    def action_confirm(self):
        """Confirme la feuille.

        Règle métier : impossible de confirmer si la feuille contient encore
        des séances planifiées dans le futur (date_acte > aujourd'hui).
        La feuille doit rester en brouillon jusqu'à ce que toutes les séances
        soient passées ou marquées Effectuées / Annulées / Non présentation.
        """
        today = fields.Date.today()
        for rec in self:
            future = rec.acte_ids.filtered(
                lambda a: a.date_acte and a.date_acte > today
                and a.state_seance == 'planifiee'
            )
            if future:
                last_future = max(future.mapped('date_acte'))
                raise UserError(_(
                    "La feuille « %s » contient des séances planifiées dans le futur "
                    "(dernière séance le %s).\n\n"
                    "La feuille ne peut pas être confirmée avant que toutes les séances "
                    "soient passées, effectuées, annulées ou marquées non-présentation."
                ) % (rec.name, last_future.strftime('%d/%m/%Y')))
        self.write({'state': 'confirmed'})

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_paid(self):
        self.write({'state': 'paid'})

    def action_cancel(self):
        """Annule la feuille et passe toutes les séances planifiées en 'Annulée'."""
        for rec in self:
            rec.acte_ids.filtered(
                lambda a: a.state_seance == 'planifiee'
            ).write({'state_seance': 'annulee'})
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_print_facture_mutuelle(self):
        self.ensure_one()
        if not self.has_mutuelle:
            raise UserError(_('Ce patient ne dispose pas de mutuelle complémentaire.'))
        report = self.env['ir.actions.report'].search([
            ('model', '=', 'cps.feuille.soins'),
            ('report_name', '=', 'os_auxiliaire_medical.report_facture_mutuelle_document'),
        ], limit=1)
        if not report:
            raise UserError(_("Le rapport de facture mutuelle est introuvable."))
        return report.report_action(self)

    def action_print_feuille(self):
        report = self.env['ir.actions.report'].search(
            [('model', '=', 'cps.feuille.soins'), ('report_type', '=', 'qweb-pdf')], limit=1)
        if not report:
            raise UserError(_("Aucune action d'impression PDF n'est disponible."))
        return report.report_action(self)

    def action_open_date_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ajouter des séances'),
            'res_model': 'cps.wizard.date.selection',
            'view_mode': 'form', 'target': 'new',
            'context': {
                'default_feuille_id': self.id,
                'default_praticien_profession': self.praticien_profession,
                'default_ordonnance_id': self.ordonnance_id.id or False,
            },
        }


class CpsActe(models.Model):
    _name = 'cps.feuille.soins.acte'
    _description = 'Acte de soin (ligne de feuille FSA25)'
    _order = 'date_acte, heure_acte, id'

    feuille_id = fields.Many2one('cps.feuille.soins', required=True, ondelete='cascade')
    acte_type_id = fields.Many2one('cps.acte.type', string="Type d'acte", ondelete='set null')
    ordonnance_ligne_id = fields.Many2one('cps.ordonnance.ligne', ondelete='set null')
    seances_restantes = fields.Integer(
        related='ordonnance_ligne_id.nb_seances_restantes', readonly=True,
    )
    seances_theorique_restantes = fields.Integer(
        string='Restantes (théor.)',
        related='ordonnance_ligne_id.nb_seances_theorique_restantes',
        readonly=True,
    )

    date_acte = fields.Date(string='Date', required=True)
    date_delay = fields.Float(
        string='Durée', compute='_compute_date_delay', store=True,
        help="Durée en jours de l'acte. "
             "Calculé automatiquement à partir de la durée de la séance en minutes."
    )

    # ── Statut de la séance ───────────────────────────────────────────────────
    state_seance = fields.Selection([
        ('planifiee',        'Planifiée'),
        ('effectuee',        'Effectuée'),
        ('annulee',          'Annulée'),
        ('non_presentation', 'Non présentation'),
    ], string='Statut',
       default='planifiee',
       tracking=True,
       help="Planifiée : séance future.\n"
            "Effectuée : séance passée réalisée.\n"
            "Annulée : séance supprimée.\n"
            "Non présentation : patient absent.")

    # ── Heure de la séance ────────────────────────────────────────────────────
    heure_acte = fields.Float(
        string='Heure',
        default=8.0,
        digits=(2, 2),
        help='Heure de début de la séance (ex : 8.5 = 8h30). '
             'Utilisée pour l\'affichage dans le calendrier.',
    )

    # ── Datetime calculé (store=True) pour la vue calendrier ─────────────────
    datetime_acte = fields.Datetime(
        string='Date/heure séance',
        compute='_compute_datetime_acte',
        store=True,
        help='Date et heure de la séance en UTC, calculé depuis date_acte + heure_acte '
             '(fuseau Pacific/Tahiti).',
    )

    @api.depends('date_acte', 'heure_acte')
    def _compute_datetime_acte(self):
        tz_tahiti = pytz.timezone(_TZ_TAHITI)
        for rec in self:
            if not rec.date_acte:
                rec.datetime_acte = False
                continue
            h = int(rec.heure_acte or 8)
            m = int(round(((rec.heure_acte or 8) - h) * 60))
            h = max(0, min(h, 23))
            m = max(0, min(m, 59))
            dt_local = dt(
                rec.date_acte.year, rec.date_acte.month, rec.date_acte.day, h, m, 0
            )
            dt_utc = tz_tahiti.localize(dt_local).astimezone(pytz.utc).replace(tzinfo=None)
            rec.datetime_acte = dt_utc

    # ── Champs related pour le popover calendrier ─────────────────────────────
    patient_id = fields.Many2one(related='feuille_id.patient_id', readonly=True, store=False)
    patient_nom = fields.Char(related='feuille_id.patient_nom', readonly=True, store=False)
    patient_prenom = fields.Char(related='feuille_id.patient_prenom', readonly=True, store=False)
    patient_dn = fields.Char(related='feuille_id.patient_dn', readonly=True, store=False)
    praticien_id = fields.Many2one(related='feuille_id.praticien_id', readonly=True, store=False)
    feuille_state = fields.Selection(related='feuille_id.state', readonly=True, store=False)
    feuille_name = fields.Char(related='feuille_id.name', readonly=True, store=False)
    montant_cps = fields.Float(related='feuille_id.montant_tiers_payant', readonly=True, store=False)
    montant_patient_feuille = fields.Float(related='feuille_id.montant_patient', readonly=True, store=False)
    name = fields.Char(compute='_compute_name', store=True)

    # ── Champs métier ─────────────────────────────────────────────────────────
    lettre_cle = fields.Char(size=10)
    coefficient = fields.Float(digits=(6, 2))
    ifd = fields.Float(default=0)
    ik = fields.Float(default=0)
    dimanche_ferie = fields.Boolean(string='Dim./Férié')
    nuit = fields.Boolean(string='Nuit')
    taux_majoration = fields.Float(default=0)
    montant = fields.Float(required=True, digits=(10, 0))

    @api.depends('acte_type_id', 'acte_type_id.duree_seance')
    def _compute_date_delay(self):
        for rec in self:
            rec.date_delay = (rec.acte_type_id.duree_seance or 30) / 60 if rec.acte_type_id.duree_seance else 0.5

    @api.depends('patient_prenom', 'patient_nom', 'lettre_cle', 'coefficient')
    def _compute_name(self):
        for rec in self:
            name = ''
            if rec.patient_id:
                name += (rec.patient_prenom or '') + ' ' + (rec.patient_nom.upper()[0] + '.' or '')
            if rec.lettre_cle:
                name += ' - ' + rec.lettre_cle or ''
            if rec.coefficient:
                name += ' - ' + rec.coefficient.__str__()
            rec.name = name

    # ── create : initialise le statut selon la date ───────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.today()
        for vals in vals_list:
            if 'state_seance' not in vals and vals.get('date_acte'):
                date_acte = vals['date_acte']
                if isinstance(date_acte, str):
                    import datetime as _dt
                    date_acte = _dt.date.fromisoformat(date_acte)
                vals['state_seance'] = 'planifiee' if date_acte > today else 'effectuee'
        return super().create(vals_list)

    # ── Onchange : met à jour le statut quand la date change ──────────────────

    @api.onchange('date_acte')
    def _onchange_date_acte_state(self):
        """Suggère le statut approprié selon la date, sauf si déjà fixé manuellement."""
        if self.state_seance in ('annulee', 'non_presentation'):
            return
        today = fields.Date.today()
        if self.date_acte:
            self.state_seance = 'planifiee' if self.date_acte > today else 'effectuee'

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id(self):
        if not self.acte_type_id:
            return
        at = self.acte_type_id
        IrParam = self.env['ir.config_parameter'].sudo()
        self.lettre_cle = at.lettre_cle
        if at.coefficient_defaut:
            self.coefficient = at.coefficient_defaut
        tarif = CpsFeuillesSoins._get_tarif_unitaire(at, IrParam)
        if at.type_supplement == 'ifn':
            montant = float(IrParam.get_param('cps.supplement.ifn', 250))
        elif at.type_supplement == 'ifd':
            montant = self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250))
        else:
            montant = round(tarif * (at.coefficient_defaut or 0), 0)
            if self.ifd:
                montant += round(self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250)), 0)
        self.montant = montant
        feuille = self.feuille_id
        if feuille and feuille.ordonnance_id and not self.ordonnance_ligne_id:
            ligne = feuille.ordonnance_id.ligne_ids.filtered(lambda l: l.acte_type_id == at)
            if ligne:
                self.ordonnance_ligne_id = ligne[0]

    @api.onchange('ifd', 'coefficient', 'lettre_cle')
    def _onchange_recalculate(self):
        IrParam = self.env['ir.config_parameter'].sudo()
        if self.acte_type_id:
            at = self.acte_type_id
            if at.type_supplement == 'ifn':
                self.montant = float(IrParam.get_param('cps.supplement.ifn', 250))
                return
            elif at.type_supplement == 'ifd':
                self.montant = round(self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250)), 0)
                return
            tarif = CpsFeuillesSoins._get_tarif_unitaire(at, IrParam)
        else:
            cfg = {'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
                   'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI': 'cps.tarif.ami',
                   'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams'}
            lk = (self.lettre_cle or '').upper()
            key = cfg.get(lk)
            fb = {'AMO': 490, 'AMK': 490, 'AMY': 490, 'AMI': 366, 'AIS': 366, 'DI': 366, 'AMS': 283, 'AMP': 283}
            tarif = float(IrParam.get_param(key, fb.get(lk, 490))) if key else 490
        montant = round(tarif * (self.coefficient or 0), 0)
        if self.ifd:
            montant += round(self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250)), 0)
        self.montant = montant

    # Ouvre la feuille de soins parente depuis le smart button.
    def action_open_feuille(self):
        self.ensure_one()
        if not self.feuille_id:
            return {}
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cps.feuille.soins',
            'res_id': self.feuille_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Mapping clé profession → libellé (répliqué localement, pas de dépendance à res.partner)
PROFESSION_LABELS = {
    'kinesitherapeute': 'Masseur-kinésithérapeute',
    'orthophoniste':    'Orthophoniste',
    'orthoptiste':      'Orthoptiste',
    'pedicure':         'Pédicure-Podologue',
    'infirmier':        'Infirmier(e)',
    'autre':            'Autre',
}
PRATICIEN_CPS_CAT = 'Praticien CPS'


def _default_praticien(env):
    return env['res.partner'].search(
        [('user_id', '=', env.uid), ('category_id.name', '=', 'Praticien CPS')], limit=1,
    )


def _profession_from_partner(partner):
    """Extrait la clé de profession depuis les catégories du partenaire."""
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
        domain="[('state', '=', 'active')]", ondelete='set null', tracking=True,
    )

    # ── Patient : computed depuis ordonnance si présente, sinon manuel ────────
    # Utilise compute+store+readonly=False pour éviter le bug "required non renseigné"
    # quand patient_id est readonly dans la vue (les champs readonly ne sont pas soumis).
    patient_id = fields.Many2one(
        'res.partner', string='Patient',
        tracking=True, ondelete='restrict',
        compute='_compute_patient_id', store=True, readonly=False,
        # required validé par constrains (pas required=True pour éviter le bug ORM)
    )
    patient_nom    = fields.Char(related='patient_id.lastname',  readonly=True)
    patient_prenom = fields.Char(related='patient_id.firstname', readonly=True)
    patient_dn     = fields.Char(related='patient_id.vat',       readonly=True, string='DN')

    @api.depends('ordonnance_id.patient_id')
    def _compute_patient_id(self):
        for rec in self:
            if rec.ordonnance_id and rec.ordonnance_id.patient_id:
                rec.patient_id = rec.ordonnance_id.patient_id
            # Si pas d'ordonnance, ne pas toucher (la valeur manuelle est conservée)

    @api.constrains('patient_id')
    def _check_patient_id(self):
        for rec in self:
            if not rec.patient_id:
                raise UserError(_('Le patient est obligatoire.'))

    # ── Praticien ─────────────────────────────────────────────────────────────

    praticien_id = fields.Many2one(
        'res.partner', string='Auxiliaire médical',
        domain="[('category_id.name', '=', 'Praticien CPS')]",
        required=True, tracking=True, ondelete='restrict',
        store=True, readonly=False,
        default=lambda self: _default_praticien(self.env),
        compute='_compute_praticien_id',
    )
    # Profession du praticien : calculée en Python depuis ses catégories,
    # sans aucun champ stocké sur res.partner
    praticien_profession = fields.Char(
        compute='_compute_praticien_profession',
        string='Profession praticien',
        store=False,
    )
    code_auxiliaire = fields.Char(related='praticien_id.vat', readonly=True, string='Code auxiliaire')
    auxiliaire_remplacant = fields.Boolean(string='Auxiliaire remplaçant')
    accord_prealable = fields.Char(string='Accord préalable n°')
    modele_id = fields.Many2one('cps.feuille.soins.modele', string='Appliquer un modèle')

    @api.depends('ordonnance_id.praticien_id')
    def _compute_praticien_id(self):
        for rec in self:
            if rec.ordonnance_id and rec.ordonnance_id.praticien_id:
                rec.praticien_id = rec.ordonnance_id.praticien_id
            # Si pas d'ordonnance, ne pas toucher (la valeur manuelle est conservée)

    @api.constrains('praticien_id')
    def _check_praticien_id(self):
        for rec in self:
            if not rec.praticien_id:
                raise UserError(_('Le praticien est obligatoire.'))

    @api.depends('praticien_id', 'praticien_id.category_id',
                 'praticien_id.category_id.parent_id')
    def _compute_praticien_profession(self):
        for rec in self:
            rec.praticien_profession = _profession_from_partner(rec.praticien_id) or ''

    parcours_soins    = fields.Boolean(default=False)
    code_prescripteur = fields.Char(string='Code prescripteur')
    date_prescription = fields.Date(string='Date de prescription', required=True)
    condition = fields.Selection([
        ('maladie', 'Maladie (défaut)'), ('longue_maladie', 'Longue Maladie'),
        ('at_mp', 'AT/MP'), ('maternite', 'Maternité'),
        ('urgence', 'Urgence'), ('autre', 'Autres dérogations'),
    ], default='maladie')
    motif_derogation = fields.Char(string='Motif de dérogation')
    num_rsr   = fields.Char(string='N° RSR')
    num_panier = fields.Char(string='N° panier de soins')

    acte_ids = fields.One2many('cps.feuille.soins.acte', 'feuille_id', string='Actes')
    montant_total        = fields.Float(compute='_compute_montants', store=True)
    montant_tiers_payant = fields.Float(compute='_compute_montants', store=True)
    montant_patient      = fields.Float(compute='_compute_montants', store=True)
    taux_remboursement   = fields.Float(string='Taux de remboursement (%)', default=70.0)

    bordereau_id     = fields.Many2one('cps.bordereau', readonly=True, tracking=True)
    date_debut_soins = fields.Date(compute='_compute_dates_soins', store=True)
    date_fin_soins   = fields.Date(compute='_compute_dates_soins', store=True)

    photo_feuille  = fields.Binary(string='Photo / scan')
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

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('ordonnance_id')
    def _onchange_ordonnance_id(self):
        if not self.ordonnance_id:
            return
        o = self.ordonnance_id
        self.patient_id       = o.patient_id
        if o.praticien_id:
            self.praticien_id = o.praticien_id
        self.date_prescription = o.date_prescription
        self.code_prescripteur = o.prescripteur_id.vat if o.prescripteur_id else ''
        self.condition         = o.condition
        self.motif_derogation  = o.motif_derogation
        self.accord_prealable  = o.accord_prealable
        self.num_rsr           = o.num_rsr
        self.num_panier        = o.num_panier

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
        def fd(d):  return d.strftime('%d%m%y') if d else ''
        def fd8(d): return d.strftime('%d%m%Y') if d else ''
        def ff(v):  return '{:,.0f}'.format(v).replace(',', ' ') if v else '0'
        sl = dict(self._fields['state'].selection)
        for rec in self:
            rec.state_texte = sl.get(rec.state, rec.state or '')
            rec.auxiliaire_remplacant_oui = 'x' if rec.auxiliaire_remplacant else ''
            rec.auxiliaire_remplacant_non = '' if rec.auxiliaire_remplacant else 'x'
            rec.parcours_soins_oui    = 'x' if rec.parcours_soins else ''
            rec.maternite_oui         = 'x' if rec.condition == 'maternite' else ''
            rec.urgence_oui           = 'x' if rec.condition == 'urgence' else ''
            rec.longue_maladie_oui    = 'x' if rec.condition == 'longue_maladie' else ''
            rec.maladie_oui           = 'x' if rec.condition == 'maladie' else ''
            rec.at_mp_oui             = 'x' if rec.condition == 'at_mp' else ''
            rec.autre_oui             = 'x' if rec.condition == 'autre' else ''
            rec.num_panier_texte       = rec.num_panier or ''
            rec.num_rsr_texte          = rec.num_rsr or ''
            rec.motif_derogation_texte = rec.motif_derogation or ''
            rec.date_prescription_texte  = fd(rec.date_prescription)
            rec.date_debut_soins_texte   = fd(rec.date_debut_soins)
            rec.date_fin_soins_texte     = fd(rec.date_fin_soins)
            rec.montant_total_texte      = ff(rec.montant_total)
            rec.montant_tiers_payant_texte = ff(rec.montant_tiers_payant)
            rec.montant_patient_texte    = ff(rec.montant_patient)
            rec.taux_remboursement_texte = '{:g}'.format(rec.taux_remboursement)
            p = rec.patient_id
            rec.patient_nom_texte    = (p.lastname.upper()  if p and p.lastname  else '')
            rec.patient_prenom_texte = (p.firstname.upper() if p and p.firstname else '')
            rec.patient_dn_texte     = (p.vat.upper()       if p and p.vat       else '')
            rec.patient_date_naissance_texte = fd8(p.birthdate_date) if p else ''
            pr = rec.praticien_id
            rec.praticien_name_texte = (pr.name or '').upper() if pr else ''
            rec.praticien_code_texte = (pr.vat  or '').upper() if pr else ''
            # Profession calculée localement via les catégories (pas de champ sur res.partner)
            rec.praticien_profession_texte = pr.get_cps_profession_label() if pr else ''
            rec.praticien_bp_texte  = (pr.street or '') if pr else ''
            rec.praticien_tel_texte = (pr.phone  or '') if pr else ''
            rec.bordereau_name_texte = (rec.bordereau_id.name or '') if rec.bordereau_id else ''
            a1 = rec.acte_ids[0] if len(rec.acte_ids) >= 1 else None
            rec.acte_01_date_texte           = fd(a1.date_acte) if a1 else ''
            rec.acte_01_lettre_cle_texte     = (a1.lettre_cle or '') if a1 else ''
            rec.acte_01_coefficient_texte    = '{:g}'.format(a1.coefficient) if a1 and a1.coefficient else ''
            rec.acte_01_ifd_texte            = ff(a1.ifd) if a1 and a1.ifd else ''
            rec.acte_01_ik_texte             = ff(a1.ik)  if a1 and a1.ik  else ''
            rec.acte_01_taux_majoration_texte = '{:g}'.format(a1.taux_majoration) if a1 and a1.taux_majoration else ''
            rec.acte_01_montant_texte        = ff(a1.montant) if a1 else ''
            rec.acte_01_dimanche_ferie_oui   = ('x' if a1.dimanche_ferie else '') if a1 else ''
            rec.acte_01_dimanche_ferie_non   = ('' if a1.dimanche_ferie else 'x') if a1 else ''
            rec.acte_01_nuit_oui             = ('x' if a1.nuit else '') if a1 else ''
            rec.acte_01_nuit_non             = ('' if a1.nuit else 'x') if a1 else ''
            a2 = rec.acte_ids[1] if len(rec.acte_ids) >= 2 else None
            rec.acte_02_date_texte           = fd(a2.date_acte) if a2 else ''
            rec.acte_02_lettre_cle_texte     = (a2.lettre_cle or '') if a2 else ''
            rec.acte_02_coefficient_texte    = '{:g}'.format(a2.coefficient) if a2 and a2.coefficient else ''
            rec.acte_02_ifd_texte            = ff(a2.ifd) if a2 and a2.ifd else ''
            rec.acte_02_ik_texte             = ff(a2.ik)  if a2 and a2.ik  else ''
            rec.acte_02_taux_majoration_texte = '{:g}'.format(a2.taux_majoration) if a2 and a2.taux_majoration else ''
            rec.acte_02_montant_texte        = ff(a2.montant) if a2 else ''
            rec.acte_02_dimanche_ferie_oui   = ('x' if a2.dimanche_ferie else '') if a2 else ''
            rec.acte_02_dimanche_ferie_non   = ('' if a2.dimanche_ferie else 'x') if a2 else ''
            rec.acte_02_nuit_oui             = ('x' if a2.nuit else '') if a2 else ''
            rec.acte_02_nuit_non             = ('' if a2.nuit else 'x') if a2 else ''

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
            rec.montant_total        = total
            rec.montant_tiers_payant = round(total * rec.taux_remboursement / 100, 0)
            rec.montant_patient      = round(total - rec.montant_tiers_payant, 0)

    @api.depends('acte_ids.date_acte')
    def _compute_dates_soins(self):
        for rec in self:
            dates = [d for d in rec.acte_ids.mapped('date_acte') if d]
            rec.date_debut_soins = min(dates) if dates else False
            rec.date_fin_soins   = max(dates) if dates else False

    @staticmethod
    def _get_tarif_unitaire(acte_type, ir_param):
        cfg = {
            'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
            'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI':  'cps.tarif.ami',
            'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams',
        }
        lk  = (acte_type.lettre_cle or '').upper()
        key = cfg.get(lk)
        return float(ir_param.get_param(key, acte_type.tarif_unitaire or 490)) if key else (acte_type.tarif_unitaire or 490)

    def action_confirm(self):   self.write({'state': 'confirmed'})
    def action_submit(self):    self.write({'state': 'submitted'})
    def action_paid(self):      self.write({'state': 'paid'})
    def action_cancel(self):    self.write({'state': 'cancelled'})
    def action_reset_draft(self): self.write({'state': 'draft'})

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
    _name  = 'cps.feuille.soins.acte'
    _description = 'Acte de soin (ligne de feuille FSA25)'
    _order = 'date_acte, id'

    feuille_id   = fields.Many2one('cps.feuille.soins', required=True, ondelete='cascade')
    acte_type_id = fields.Many2one('cps.acte.type', string="Type d'acte", ondelete='set null')
    ordonnance_ligne_id = fields.Many2one('cps.ordonnance.ligne', ondelete='set null')
    seances_restantes   = fields.Integer(
        related='ordonnance_ligne_id.nb_seances_restantes', readonly=True,
    )

    date_acte       = fields.Date(string='Date', required=True)
    lettre_cle      = fields.Char(size=10)
    coefficient     = fields.Float(digits=(6, 2))
    ifd             = fields.Float(default=0)
    ik              = fields.Float(default=0)
    dimanche_ferie  = fields.Boolean(string='Dim./Férié')
    nuit            = fields.Boolean(string='Nuit')
    taux_majoration = fields.Float(default=0)
    montant         = fields.Float(required=True, digits=(10, 0))

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id(self):
        if not self.acte_type_id:
            return
        at = self.acte_type_id
        IrParam = self.env['ir.config_parameter'].sudo()
        self.lettre_cle  = at.lettre_cle
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
                self.montant = float(IrParam.get_param('cps.supplement.ifn', 250)); return
            elif at.type_supplement == 'ifd':
                self.montant = round(self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250)), 0); return
            tarif = CpsFeuillesSoins._get_tarif_unitaire(at, IrParam)
        else:
            cfg = {'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
                   'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI':  'cps.tarif.ami',
                   'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams'}
            lk  = (self.lettre_cle or '').upper()
            key = cfg.get(lk)
            fb  = {'AMO': 490, 'AMK': 490, 'AMY': 490, 'AMI': 366, 'AIS': 366, 'DI': 366, 'AMS': 283, 'AMP': 283}
            tarif = float(IrParam.get_param(key, fb.get(lk, 490))) if key else 490
        montant = round(tarif * (self.coefficient or 0), 0)
        if self.ifd:
            montant += round(self.ifd * float(IrParam.get_param('cps.supplement.ifd', 250)), 0)
        self.montant = montant

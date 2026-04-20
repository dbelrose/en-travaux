"""
Extension de res.partner pour le module CPS.

Principe strict : AUCUN champ custom créant une colonne sur res_partner.
Seuls des champs compute sans store=True et des One2many (FK portée par
l'autre table) sont ajoutés.

Rôles CPS = étiquettes (category_id) uniquement :
  • « Praticien CPS »  + sous-catégories par profession
  • « Patient CPS »
  • « Prescripteur »
"""
from odoo import models, fields, api, _

# Mapping nom de catégorie profession → clé de sélection
PROFESSION_CAT_TO_KEY = {
    'Masseur-kinésithérapeute': 'kinesitherapeute',
    'Orthophoniste':            'orthophoniste',
    'Orthoptiste':              'orthoptiste',
    'Pédicure-Podologue':       'pedicure',
    'Infirmier(e)':             'infirmier',
    'Autre auxiliaire médical': 'autre',
}
PROFESSION_KEY_TO_LABEL = {
    'kinesitherapeute': 'Masseur-kinésithérapeute',
    'orthophoniste':    'Orthophoniste',
    'orthoptiste':      'Orthoptiste',
    'pedicure':         'Pédicure-Podologue',
    'infirmier':        'Infirmier(e)',
    'autre':            'Autre',
}
PROFESSION_XMLIDS = {
    'kinesitherapeute': 'os_auxiliaire_medical.partner_category_kinesitherapeute',
    'orthophoniste':    'os_auxiliaire_medical.partner_category_orthophoniste',
    'orthoptiste':      'os_auxiliaire_medical.partner_category_orthoptiste',
    'pedicure':         'os_auxiliaire_medical.partner_category_pedicure',
    'infirmier':        'os_auxiliaire_medical.partner_category_infirmier',
    'autre':            'os_auxiliaire_medical.partner_category_autre_praticien',
}

CAT_PRATICIEN    = 'Praticien CPS'
CAT_PATIENT      = 'Patient CPS'
CAT_PRESCRIPTEUR = 'Prescripteur'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Booléens de rôle (compute, store=False → pas de colonne DB) ──────────
    is_praticien_cps = fields.Boolean(compute='_compute_cps_flags')
    is_patient_cps   = fields.Boolean(compute='_compute_cps_flags')
    is_prescripteur  = fields.Boolean(compute='_compute_cps_flags')
    is_cps           = fields.Boolean(compute='_compute_cps_flags')

    @api.depends('category_id', 'category_id.name', 'category_id.parent_id.name')
    def _compute_cps_flags(self):
        for rec in self:
            cat_names    = set(rec.category_id.mapped('name'))
            parent_names = set(rec.category_id.mapped('parent_id.name'))
            rec.is_praticien_cps = CAT_PRATICIEN in (cat_names | parent_names)
            rec.is_patient_cps   = CAT_PATIENT   in cat_names
            rec.is_prescripteur  = CAT_PRESCRIPTEUR in cat_names
            rec.is_cps = rec.is_praticien_cps or rec.is_patient_cps or rec.is_prescripteur

    # ── Statistiques (One2many → FK sur l'autre table, pas de colonne ici) ───
    cps_feuille_patient_ids = fields.One2many(
        'cps.feuille.soins', 'patient_id', string='Feuilles (patient)',
    )
    cps_feuille_patient_count = fields.Integer(compute='_compute_cps_counts')

    cps_feuille_praticien_ids = fields.One2many(
        'cps.feuille.soins', 'praticien_id', string='Feuilles (praticien)',
    )
    cps_feuille_praticien_count = fields.Integer(compute='_compute_cps_counts')

    cps_bordereau_ids = fields.One2many('cps.bordereau', 'praticien_id', string='Bordereaux')
    cps_bordereau_count = fields.Integer(compute='_compute_cps_counts')

    @api.depends(
        'cps_feuille_patient_ids', 'cps_feuille_praticien_ids', 'cps_bordereau_ids',
    )
    def _compute_cps_counts(self):
        for rec in self:
            rec.cps_feuille_patient_count   = len(rec.cps_feuille_patient_ids)
            rec.cps_feuille_praticien_count = len(rec.cps_feuille_praticien_ids)
            rec.cps_bordereau_count         = len(rec.cps_bordereau_ids)

    # ── Helper : profession à partir des catégories (pas de champ stocké) ────

    # ── Champ profession affiché (compute, pas de colonne DB) ────────────────
    cps_profession = fields.Char(
        compute='_compute_cps_profession',
        string='Profession',
        store=False,
    )

    @api.depends('category_id', 'category_id.name', 'category_id.parent_id.name')
    def _compute_cps_profession(self):
        for rec in self:
            rec.cps_profession = rec.get_cps_profession_label()

    def get_cps_profession_key(self):
        """
        Retourne la clé de sélection de profession depuis category_id.
        Ex : 'orthophoniste'  — None si pas de sous-catégorie trouvée.
        Utilisé par les autres modèles pour éviter tout champ sur res.partner.
        """
        self.ensure_one()
        for cat in self.category_id:
            if cat.parent_id and cat.parent_id.name == CAT_PRATICIEN:
                return PROFESSION_CAT_TO_KEY.get(cat.name)
        return None

    def get_cps_profession_label(self):
        """Retourne le libellé lisible de la profession, ou ''."""
        self.ensure_one()
        key = self.get_cps_profession_key()
        return PROFESSION_KEY_TO_LABEL.get(key, '') if key else ''

    def set_cps_profession(self, profession_key):
        """
        Pose la sous-catégorie profession correspondante sur ce partenaire.
        Retire d'abord les éventuelles anciennes sous-catégories de profession.
        """
        self.ensure_one()
        # Toutes les sous-catégories de profession connues
        all_prof_cats = self.env['res.partner.category'].search([
            ('parent_id.name', '=', CAT_PRATICIEN),
        ])
        old = self.category_id.filtered(lambda c: c in all_prof_cats)
        if old:
            self.write({'category_id': [(3, c.id) for c in old]})
        if profession_key:
            xmlid = PROFESSION_XMLIDS.get(profession_key)
            if xmlid:
                cat = self.env.ref(xmlid, raise_if_not_found=False)
                if cat:
                    self.write({'category_id': [(4, cat.id)]})

    # ── Actions stat buttons ──────────────────────────────────────────────────

    def action_view_feuilles_patient(self):
        return {'type': 'ir.actions.act_window', 'name': _('Feuilles de soins (patient)'),
                'res_model': 'cps.feuille.soins', 'view_mode': 'list,form',
                'domain': [('patient_id', '=', self.id)]}

    def action_view_feuilles_praticien(self):
        return {'type': 'ir.actions.act_window', 'name': _('Feuilles de soins (praticien)'),
                'res_model': 'cps.feuille.soins', 'view_mode': 'list,form',
                'domain': [('praticien_id', '=', self.id)]}

    def action_view_bordereaux(self):
        return {'type': 'ir.actions.act_window', 'name': _('Bordereaux'),
                'res_model': 'cps.bordereau', 'view_mode': 'list,form',
                'domain': [('praticien_id', '=', self.id)]}

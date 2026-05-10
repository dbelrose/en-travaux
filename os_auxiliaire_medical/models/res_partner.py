"""
Extension de res.partner pour le module CPS.

Principe strict : AUCUN champ custom créant une colonne sur res_partner.
Seuls des champs compute sans store=True et des One2many (FK portée par
l'autre table) sont ajoutés.
"""
from odoo import models, fields, api, _

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

_XMLID_PRATICIEN    = 'os_auxiliaire_medical.partner_category_praticien'
_XMLID_PATIENT      = 'os_auxiliaire_medical.partner_category_patient'
_XMLID_PRESCRIPTEUR = 'os_auxiliaire_medical.partner_category_prescripteur'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ── Booléens de rôle ──────────────────────────────────────────────────────
    is_praticien_cps = fields.Boolean(compute='_compute_cps_flags')
    is_patient_cps   = fields.Boolean(compute='_compute_cps_flags')
    is_prescripteur  = fields.Boolean(compute='_compute_cps_flags')
    is_cps           = fields.Boolean(compute='_compute_cps_flags')

    @api.depends('category_id', 'category_id.parent_id')
    def _compute_cps_flags(self):
        Ref = self.env.ref
        cat_praticien    = Ref(_XMLID_PRATICIEN,    raise_if_not_found=False)
        cat_patient      = Ref(_XMLID_PATIENT,      raise_if_not_found=False)
        cat_prescripteur = Ref(_XMLID_PRESCRIPTEUR, raise_if_not_found=False)
        for rec in self:
            cats        = rec.category_id
            parent_cats = cats.mapped('parent_id')
            rec.is_praticien_cps = bool(
                cat_praticien and (cat_praticien in cats or cat_praticien in parent_cats)
            )
            rec.is_patient_cps   = bool(cat_patient      and cat_patient      in cats)
            rec.is_prescripteur  = bool(cat_prescripteur and cat_prescripteur in cats)
            rec.is_cps = rec.is_praticien_cps or rec.is_patient_cps or rec.is_prescripteur

    # ── Champs related « vat » ────────────────────────────────────────────────
    cps_vat_praticien = fields.Char(
        related='vat', string='Code auxiliaire médical (CPS)',
        store=False, readonly=False,
    )
    cps_vat_patient = fields.Char(
        related='vat', string='N° DN (matricule CPS)',
        store=False, readonly=False,
    )
    cps_vat_prescripteur = fields.Char(
        related='vat', string='Code prescripteur (AM/RPPS)',
        store=False, readonly=False,
    )

    # ── Relations patient ─────────────────────────────────────────────────────
    cps_feuille_patient_ids = fields.One2many(
        'cps.feuille.soins', 'patient_id', string='Feuilles (patient)',
    )
    cps_feuille_patient_count = fields.Integer(compute='_compute_cps_counts')

    cps_ordonnance_patient_ids = fields.One2many(
        'cps.ordonnance', 'patient_id', string='Ordonnances (patient)',
    )
    cps_ordonnance_count        = fields.Integer(compute='_compute_cps_patient_stats', string='Nb ordonnances')
    cps_bordereau_patient_count = fields.Integer(compute='_compute_cps_patient_stats', string='Nb bordereaux')
    cps_prescripteur_count      = fields.Integer(compute='_compute_cps_patient_stats', string='Nb prescripteurs')
    cps_praticien_count         = fields.Integer(compute='_compute_cps_patient_stats', string='Nb praticiens')

    # ── Relations praticien ───────────────────────────────────────────────────
    cps_feuille_praticien_ids = fields.One2many(
        'cps.feuille.soins', 'praticien_id', string='Feuilles (praticien)',
    )
    cps_feuille_praticien_count = fields.Integer(compute='_compute_cps_counts')

    cps_bordereau_ids   = fields.One2many('cps.bordereau', 'praticien_id', string='Bordereaux')
    cps_bordereau_count = fields.Integer(compute='_compute_cps_counts')

    # ── Compute compteurs ─────────────────────────────────────────────────────
    @api.depends(
        'cps_feuille_patient_ids',
        'cps_feuille_praticien_ids',
        'cps_bordereau_ids',
    )
    def _compute_cps_counts(self):
        for rec in self:
            rec.cps_feuille_patient_count   = len(rec.cps_feuille_patient_ids)
            rec.cps_feuille_praticien_count = len(rec.cps_feuille_praticien_ids)
            rec.cps_bordereau_count         = len(rec.cps_bordereau_ids)

    @api.depends(
        'cps_ordonnance_patient_ids',
        'cps_ordonnance_patient_ids.prescripteur_id',
        'cps_feuille_patient_ids',
        'cps_feuille_patient_ids.praticien_id',
        'cps_feuille_patient_ids.bordereau_id',
    )
    def _compute_cps_patient_stats(self):
        for rec in self:
            ordonnances = rec.cps_ordonnance_patient_ids
            rec.cps_ordonnance_count        = len(ordonnances)
            feuilles = rec.cps_feuille_patient_ids
            rec.cps_bordereau_patient_count = len(feuilles.mapped('bordereau_id').filtered('id'))
            rec.cps_prescripteur_count      = len(ordonnances.mapped('prescripteur_id').filtered('id'))
            rec.cps_praticien_count         = len(feuilles.mapped('praticien_id').filtered('id'))

    # ── Profession ────────────────────────────────────────────────────────────
    cps_profession = fields.Char(
        compute='_compute_cps_profession', string='Profession', store=False,
    )

    @api.depends('category_id', 'category_id.parent_id')
    def _compute_cps_profession(self):
        for rec in self:
            rec.cps_profession = rec.get_cps_profession_label()

    def get_cps_profession_key(self):
        self.ensure_one()
        cat_praticien = self.env.ref(_XMLID_PRATICIEN, raise_if_not_found=False)
        if not cat_praticien:
            return None
        for cat in self.category_id:
            if cat.parent_id == cat_praticien:
                return PROFESSION_CAT_TO_KEY.get(cat.name)
        return None

    def get_cps_profession_label(self):
        self.ensure_one()
        key = self.get_cps_profession_key()
        return PROFESSION_KEY_TO_LABEL.get(key, '') if key else ''

    def set_cps_profession(self, profession_key):
        self.ensure_one()
        cat_praticien = self.env.ref(_XMLID_PRATICIEN, raise_if_not_found=False)
        all_prof_cats = self.env['res.partner.category'].search([
            ('parent_id', '=', cat_praticien.id if cat_praticien else False),
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

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'company_id' in fields_list and not res.get('company_id'):
            res['company_id'] = self.env.company.id
        return res

    # ── Actions praticien ─────────────────────────────────────────────────────
    def action_view_feuilles_praticien(self):
        return {'type': 'ir.actions.act_window', 'name': _('Feuilles de soins (praticien)'),
                'res_model': 'cps.feuille.soins', 'view_mode': 'tree,form',
                'domain': [('praticien_id', '=', self.id)]}

    def action_view_bordereaux(self):
        return {'type': 'ir.actions.act_window', 'name': _('Bordereaux'),
                'res_model': 'cps.bordereau', 'view_mode': 'tree,form',
                'domain': [('praticien_id', '=', self.id)]}

    # ── Actions patient ───────────────────────────────────────────────────────
    def action_view_feuilles_patient(self):
        return {'type': 'ir.actions.act_window', 'name': _('Feuilles de soins'),
                'res_model': 'cps.feuille.soins', 'view_mode': 'tree,form',
                'domain': [('patient_id', '=', self.id)]}

    def action_view_ordonnances_patient(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Ordonnances'),
                'res_model': 'cps.ordonnance', 'view_mode': 'tree,form',
                'domain': [('patient_id', '=', self.id)],
                'context': {'default_patient_id': self.id}}

    def action_view_bordereaux_patient(self):
        self.ensure_one()
        bordereau_ids = self.env['cps.bordereau'].search([
            ('feuille_ids.patient_id', '=', self.id)
        ]).ids
        return {'type': 'ir.actions.act_window', 'name': _('Bordereaux'),
                'res_model': 'cps.bordereau', 'view_mode': 'tree,form',
                'domain': [('id', 'in', bordereau_ids)]}

    def action_view_prescripteurs_patient(self):
        self.ensure_one()
        ids = self.cps_ordonnance_patient_ids.mapped('prescripteur_id').ids
        return {'type': 'ir.actions.act_window', 'name': _('Prescripteurs'),
                'res_model': 'res.partner', 'view_mode': 'tree,form',
                'domain': [('id', 'in', ids)],
                'context': {'search_default_customer_rank': 0}}

    def action_view_praticiens_patient(self):
        self.ensure_one()
        ids = self.cps_feuille_patient_ids.mapped('praticien_id').ids
        return {'type': 'ir.actions.act_window', 'name': _('Praticiens'),
                'res_model': 'res.partner', 'view_mode': 'tree,form',
                'domain': [('id', 'in', ids)],
                'context': {'search_default_customer_rank': 0}}

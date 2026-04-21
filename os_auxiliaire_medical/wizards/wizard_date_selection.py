"""
Wizard de saisie groupée de séances par sélection calendaire – v5.
date_fin par défaut = ordonnance.date_fin_validite (via default function).
"""
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardDateSelection(models.TransientModel):
    _name = 'cps.wizard.date.selection'
    _description = 'Saisie de séances par sélection calendaire'

    feuille_id = fields.Many2one('cps.feuille.soins', required=True, ondelete='cascade')
    praticien_profession = fields.Char(related='feuille_id.praticien_profession', readonly=True)
    ordonnance_id = fields.Many2one('cps.ordonnance', related='feuille_id.ordonnance_id', readonly=True)

    # ── Acte (facultatif) ─────────────────────────────────────────────────────
    acte_type_id = fields.Many2one(
        'cps.acte.type', string="Type d'acte (facultatif)",
        help='Laisser vide pour distribution automatique sur les actes de l\'ordonnance.',
    )
    acte_type_ids_disponibles = fields.Many2many(
        'cps.acte.type', 'wizard_date_acte_dispo_rel', 'wizard_id', 'acte_type_id',
        compute='_compute_actes_disponibles',
    )

    ifd = fields.Float(string='IFD (unités)', default=0)
    dimanche_ferie = fields.Boolean(string='Dim./Férié')
    nuit = fields.Boolean(string='Nuit')
    delai_min_jours = fields.Integer(
        string='Délai min entre 2 séances (j)',
        compute='_compute_delai_min', store=True, readonly=False,
    )

    # ── Plage de dates ────────────────────────────────────────────────────────
    date_debut = fields.Date(string='Du', required=True, default=fields.Date.today)
    date_fin = fields.Date(string='Au')
    nb_seances = fields.Integer(string='Nombre de séances')

    # ── Jours (checkboxes standards) ──────────────────────────────────────────
    lundi        = fields.Boolean(string='Lundi',    default=True)
    mardi        = fields.Boolean(string='Mardi',    default=False)
    mercredi     = fields.Boolean(string='Mercredi', default=False)
    jeudi        = fields.Boolean(string='Jeudi',    default=False)
    vendredi     = fields.Boolean(string='Vendredi', default=False)
    samedi       = fields.Boolean(string='Samedi',   default=False)
    dimanche_jour = fields.Boolean(string='Dimanche', default=False)

    ligne_ids = fields.One2many('cps.wizard.date.selection.ligne', 'wizard_id')
    nb_selectionnees = fields.Integer(compute='_compute_stats')
    montant_total_estime = fields.Float(compute='_compute_stats', digits=(10, 0))
    nb_non_assignees = fields.Integer(compute='_compute_stats')

    # ── Default date_fin via context (fonctionne pour TransientModel) ─────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'date_fin' in fields_list:
            ordonnance_id = res.get('ordonnance_id') or self.env.context.get('default_ordonnance_id')
            if ordonnance_id:
                ordonnance = self.env['cps.ordonnance'].browse(ordonnance_id)
                if ordonnance.date_fin_validite:
                    res['date_fin'] = ordonnance.date_fin_validite
        return res

    @api.onchange('ordonnance_id')
    def _onchange_ordonnance_date_fin(self):
        if self.ordonnance_id and self.ordonnance_id.date_fin_validite:
            self.date_fin = self.ordonnance_id.date_fin_validite

    # ── Compute ───────────────────────────────────────────────────────────────

    @api.depends('ordonnance_id')
    def _compute_actes_disponibles(self):
        for rec in self:
            if rec.ordonnance_id:
                rec.acte_type_ids_disponibles = rec.ordonnance_id.ligne_ids.mapped('acte_type_id')
            else:
                rec.acte_type_ids_disponibles = self.env['cps.acte.type']

    @api.depends('acte_type_id.delai_min_jours')
    def _compute_delai_min(self):
        for rec in self:
            rec.delai_min_jours = rec.acte_type_id.delai_min_jours if rec.acte_type_id else 0

    @api.depends('ligne_ids.selected', 'ligne_ids.montant', 'ligne_ids.acte_type_id')
    def _compute_stats(self):
        for rec in self:
            sel = rec.ligne_ids.filtered('selected')
            rec.nb_selectionnees = len(sel)
            rec.montant_total_estime = sum(sel.mapped('montant'))
            rec.nb_non_assignees = len(sel.filtered(lambda l: not l.acte_type_id))

    # ── Génération des dates ──────────────────────────────────────────────────

    def action_generer_dates(self):
        self.ensure_one()
        if self.date_fin and self.date_debut > self.date_fin:
            raise UserError(_('La date de début doit être ≤ à la date de fin.'))
        if self.date_fin and self.nb_seances:
            raise UserError(_('Choisir un et un seul des deux critères entre la date de fin et le nombre de séances.'))
        if self.date_fin is None and self.nb_seances is None:
            raise UserError(_('Choisir un et un seul des deux critères entre la date de fin et le nombre de séances.'))
        jours = []
        for coché, idx in [
            (self.lundi, 0), (self.mardi, 1), (self.mercredi, 2), (self.jeudi, 3),
            (self.vendredi, 4), (self.samedi, 5), (self.dimanche_jour, 6),
        ]:
            if coché:
                jours.append(idx)
        if not jours:
            raise UserError(_('Cochez au moins un jour de la semaine.'))

        dates = []
        current = self.date_debut
        while current <= self.date_fin or len(dates) <= self.nb_seances:
            if current.weekday() in jours:
                dates.append(current)
            current += datetime.timedelta(days=1)
        if not dates:
            raise UserError(_('Aucune date ne correspond à la sélection.'))

        IrParam = self.env['ir.config_parameter'].sudo()
        if self.acte_type_id:
            montant_u = self._montant_unitaire(self.acte_type_id, IrParam)
            ord_ligne = False
            if self.ordonnance_id:
                ol = self.ordonnance_id.ligne_ids.filtered(lambda l: l.acte_type_id == self.acte_type_id)
                ord_ligne = ol[0] if ol else False
            nouvelles = [(0, 0, {
                'date': d, 'selected': True,
                'acte_type_id': self.acte_type_id.id,
                'ordonnance_ligne_id': ord_ligne.id if ord_ligne else False,
                'montant': montant_u, 'warning': '',
            }) for d in dates]
        elif self.ordonnance_id:
            nouvelles = self._distribuer_dates_auto(dates, IrParam)
        else:
            nouvelles = [(0, 0, {
                'date': d, 'selected': True,
                'acte_type_id': False, 'ordonnance_ligne_id': False,
                'montant': 0.0, 'warning': _('Aucun acte assigné'),
            }) for d in dates]

        self.ligne_ids = [(5, 0, 0)] + nouvelles
        return self._reopen()

    def _distribuer_dates_auto(self, dates, IrParam):
        lignes_ord = self.ordonnance_id.ligne_ids.sorted(
            lambda l: (l.acte_type_id.sequence or 0, l.id)
        ).filtered(lambda l: l.nb_seances_restantes > 0)
        if not lignes_ord:
            return [(0, 0, {'date': d, 'selected': False, 'acte_type_id': False,
                            'ordonnance_ligne_id': False, 'montant': 0.0,
                            'warning': _('Séances épuisées')}) for d in dates]
        remaining = {l.id: l.nb_seances_restantes for l in lignes_ord}
        last_date = {l.id: l.get_last_seance_date() for l in lignes_ord}
        montants = {l.id: self._montant_unitaire(l.acte_type_id, IrParam) for l in lignes_ord}
        delai_global = self.delai_min_jours
        result = []
        for date in sorted(dates):
            assigned = False
            for ligne in lignes_ord:
                if remaining.get(ligne.id, 0) <= 0:
                    continue
                delai = max(ligne.acte_type_id.delai_min_jours or 0, delai_global)
                last = last_date.get(ligne.id)
                if last and delai > 0 and (date - last).days < delai:
                    continue
                result.append((0, 0, {
                    'date': date, 'selected': True,
                    'acte_type_id': ligne.acte_type_id.id,
                    'ordonnance_ligne_id': ligne.id,
                    'montant': montants[ligne.id], 'warning': '',
                }))
                remaining[ligne.id] -= 1
                last_date[ligne.id] = date
                assigned = True
                break
            if not assigned:
                result.append((0, 0, {
                    'date': date, 'selected': False,
                    'acte_type_id': False, 'ordonnance_ligne_id': False,
                    'montant': 0.0, 'warning': _('Non assignée : épuisé ou délai non respecté'),
                }))
        return result

    @staticmethod
    def _montant_unitaire(acte_type, IrParam):
        if not acte_type:
            return 0.0
        if acte_type.type_supplement == 'ifn':
            return float(IrParam.get_param('cps.supplement.ifn', 250))
        cfg = {'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
               'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI': 'cps.tarif.ami',
               'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams'}
        lk = (acte_type.lettre_cle or '').upper()
        key = cfg.get(lk)
        tarif = float(IrParam.get_param(key, acte_type.tarif_unitaire or 490)) if key else (acte_type.tarif_unitaire or 490)
        return round(tarif * (acte_type.coefficient_defaut or 0), 0)

    def action_appliquer(self):
        self.ensure_one()
        sel = self.ligne_ids.filtered('selected')
        if not sel:
            raise UserError(_('Aucune date sélectionnée.'))
        lignes = []
        for l in sel.sorted('date'):
            lignes.append((0, 0, {
                'acte_type_id': l.acte_type_id.id if l.acte_type_id else False,
                'date_acte': l.date,
                'lettre_cle': l.acte_type_id.lettre_cle if l.acte_type_id else False,
                'coefficient': l.acte_type_id.coefficient_defaut if l.acte_type_id else 0,
                'ifd': self.ifd, 'dimanche_ferie': self.dimanche_ferie, 'nuit': self.nuit,
                'montant': l.montant,
                'ordonnance_ligne_id': l.ordonnance_ligne_id.id if l.ordonnance_ligne_id else False,
            }))
        self.feuille_id.write({'acte_ids': lignes})
        return {'type': 'ir.actions.act_window', 'res_model': 'cps.feuille.soins',
                'res_id': self.feuille_id.id, 'view_mode': 'form', 'target': 'current'}

    def action_tout_selectionner(self):
        self.ligne_ids.write({'selected': True})
        return self._reopen()

    def action_tout_deselectionner(self):
        self.ligne_ids.write({'selected': False})
        return self._reopen()

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new',
                'context': self.env.context}


class WizardDateSelectionLigne(models.TransientModel):
    _name = 'cps.wizard.date.selection.ligne'
    _description = 'Ligne de date (wizard saisie séances)'
    _order = 'date'

    wizard_id = fields.Many2one('cps.wizard.date.selection', required=True, ondelete='cascade')
    date = fields.Date(required=True)
    selected = fields.Boolean(string='✓', default=True)
    jour_semaine = fields.Char(compute='_compute_jour', readonly=True)
    acte_type_id = fields.Many2one('cps.acte.type', string='Acte')
    ordonnance_ligne_id = fields.Many2one('cps.ordonnance.ligne', readonly=True)
    montant = fields.Float(digits=(10, 0))
    warning = fields.Char(readonly=True)

    @api.depends('date')
    def _compute_jour(self):
        j = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
        for rec in self:
            rec.jour_semaine = j[rec.date.weekday()] if rec.date else ''

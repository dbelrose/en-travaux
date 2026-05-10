"""
Wizard de saisie groupée de séances par sélection calendaire – v9.

Nouveautés v9 :
  • Plus de limite à 16 séances : le wizard crée autant de feuilles FSA25
    que nécessaire (16 actes par feuille = limite du formulaire papier).
  • nb_seances initialisé depuis les séances restantes de l'ordonnance
    (ou de l'acte sélectionné).
  • Colonne « Feuille n° » prévisionnelle dans le tableau des dates.

Règles du critère de fin :
  • date_fin seul  → toutes les dates jusqu'à date_fin
  • nb_seances seul → exactement N séances
  • aucun des deux  → séances restantes de l'ordonnance
  • les deux → UserError
"""
import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

# Nombre de lignes actes sur un formulaire FSA25 papier
SEANCES_PAR_FEUILLE = 16


class WizardDateSelection(models.TransientModel):
    _name = 'cps.wizard.date.selection'
    _description = 'Saisie de séances par sélection calendaire'

    feuille_id           = fields.Many2one('cps.feuille.soins', required=True, ondelete='cascade')
    praticien_profession = fields.Char(related='feuille_id.praticien_profession', readonly=True)
    ordonnance_id        = fields.Many2one('cps.ordonnance', related='feuille_id.ordonnance_id', readonly=True)

    # ── Acte (facultatif) ─────────────────────────────────────────────────────
    acte_type_id = fields.Many2one(
        'cps.acte.type', string="Type d'acte (facultatif)",
        help="Laisser vide pour distribution automatique sur les actes de l'ordonnance.",
    )
    acte_type_ids_disponibles = fields.Many2many(
        'cps.acte.type', 'wizard_date_acte_dispo_rel', 'wizard_id', 'acte_type_id',
        compute='_compute_actes_disponibles',
    )

    ifd             = fields.Float(string='IFD (unités)', default=0)
    dimanche_ferie  = fields.Boolean(string='Dim./Férié')
    nuit            = fields.Boolean(string='Nuit')
    delai_min_jours = fields.Integer(
        string='Délai min entre 2 séances (j)',
        compute='_compute_delai_min', store=True, readonly=False,
    )

    # ── Heure commune à toutes les séances générées ───────────────────────────
    heure_debut = fields.Float(
        string='Heure de début',
        default=8.0,
        digits=(2, 2),
        help='Heure de début commune à toutes les séances (ex : 8.5 = 8h30). '
             'Peut être ajustée ligne par ligne avant d\'appliquer.',
    )

    # ── Critères de fin (facultatifs, mutuellement exclusifs) ─────────────────
    date_debut = fields.Date(string='Du', required=True, default=fields.Date.today)
    date_fin   = fields.Date(
        string='Au',
        help='Optionnel – exclusif avec « Nombre de séances ».\n'
             'Génère toutes les dates jusqu\'à cette date.',
    )
    nb_seances = fields.Integer(
        string='Nombre de séances',
        help='Optionnel – exclusif avec « Date de fin ».\n'
             'Initialisé automatiquement depuis les séances restantes de l\'ordonnance.\n'
             'Le wizard créera autant de feuilles FSA25 que nécessaire (16 actes / feuille).',
    )

    # ── Jours de la semaine ───────────────────────────────────────────────────
    lundi         = fields.Boolean(string='Lundi',    default=True)
    mardi         = fields.Boolean(string='Mardi',    default=False)
    mercredi      = fields.Boolean(string='Mercredi', default=False)
    jeudi         = fields.Boolean(string='Jeudi',    default=False)
    vendredi      = fields.Boolean(string='Vendredi', default=False)
    samedi        = fields.Boolean(string='Samedi',   default=False)
    dimanche_jour = fields.Boolean(string='Dimanche', default=False)

    ligne_ids               = fields.One2many('cps.wizard.date.selection.ligne', 'wizard_id')
    nb_selectionnees        = fields.Integer(compute='_compute_stats')
    montant_total_estime    = fields.Float(compute='_compute_stats', digits=(10, 0))
    nb_non_assignees        = fields.Integer(compute='_compute_stats')
    nb_feuilles_necessaires = fields.Integer(compute='_compute_stats',
                                             string='Feuilles FSA25 nécessaires')

    # ── default_get : initialise nb_seances depuis l'ordonnance ──────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ordonnance_id = (
            res.get('ordonnance_id')
            or self.env.context.get('default_ordonnance_id')
        )
        if ordonnance_id and 'nb_seances' in fields_list:
            ordonnance = self.env['cps.ordonnance'].browse(ordonnance_id)
            total = sum(ordonnance.ligne_ids.mapped('nb_seances_restantes'))
            if total > 0:
                res['nb_seances'] = total
        return res

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
            n = len(sel)
            rec.nb_selectionnees        = n
            rec.montant_total_estime    = sum(sel.mapped('montant'))
            rec.nb_non_assignees        = len(sel.filtered(lambda l: not l.acte_type_id))
            rec.nb_feuilles_necessaires = (
                (n + SEANCES_PAR_FEUILLE - 1) // SEANCES_PAR_FEUILLE if n > 0 else 0
            )

    # ── Onchanges ─────────────────────────────────────────────────────────────

    @api.onchange('heure_debut')
    def _onchange_heure_debut(self):
        """Propage l'heure commune sur toutes les lignes déjà générées."""
        for ligne in self.ligne_ids:
            ligne.heure_acte = self.heure_debut

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id_seances(self):
        """Met à jour nb_seances depuis l'ordonnance lors du choix d'un type d'acte."""
        if self.acte_type_id and self.ordonnance_id:
            ligne = self.ordonnance_id.ligne_ids.filtered(
                lambda l: l.acte_type_id == self.acte_type_id
            )
            if ligne:
                self.nb_seances = ligne[0].nb_seances_restantes
        elif self.ordonnance_id and not self.acte_type_id:
            # Totalité des séances restantes toutes lignes confondues
            self.nb_seances = sum(
                self.ordonnance_id.ligne_ids.mapped('nb_seances_restantes')
            )

    # ── Action principale ─────────────────────────────────────────────────────

    def action_generer_dates(self):
        self.ensure_one()

        has_date_fin   = bool(self.date_fin)
        has_nb_seances = bool(self.nb_seances)

        if has_date_fin and has_nb_seances:
            raise UserError(_(
                'Indiquez soit une date de fin, soit un nombre de séances — pas les deux.'
            ))
        if has_date_fin and self.date_debut > self.date_fin:
            raise UserError(_('La date de début doit être ≤ à la date de fin.'))

        jours = [idx for coché, idx in [
            (self.lundi, 0), (self.mardi, 1), (self.mercredi, 2), (self.jeudi, 3),
            (self.vendredi, 4), (self.samedi, 5), (self.dimanche_jour, 6),
        ] if coché]
        if not jours:
            raise UserError(_('Cochez au moins un jour de la semaine.'))

        # Nombre max de séances à générer
        if has_nb_seances:
            nb_max = self.nb_seances
        elif not has_date_fin:
            if not self.ordonnance_id:
                raise UserError(_(
                    'Sans date de fin ni nombre de séances, une ordonnance est requise '
                    'pour déterminer automatiquement le nombre de séances à planifier.'
                ))
            nb_max = sum(self.ordonnance_id.ligne_ids.mapped('nb_seances_restantes'))
            if nb_max <= 0:
                raise UserError(_("L'ordonnance ne contient plus de séances disponibles."))
        else:
            nb_max = 9999  # date_fin seule — pas de limite théorique

        # Génération des dates
        dates = []
        current = self.date_debut
        safety  = 3650  # 10 ans max
        while safety > 0:
            safety -= 1
            if has_date_fin and current > self.date_fin:
                break
            if len(dates) >= nb_max:
                break
            if current.weekday() in jours:
                dates.append(current)
            current += datetime.timedelta(days=1)

        if not dates:
            raise UserError(_('Aucune date ne correspond à la sélection.'))

        IrParam = self.env['ir.config_parameter'].sudo()
        heure   = self.heure_debut

        if self.acte_type_id:
            montant_u = self._montant_unitaire(self.acte_type_id, IrParam)
            ord_ligne = False
            if self.ordonnance_id:
                ol = self.ordonnance_id.ligne_ids.filtered(
                    lambda l: l.acte_type_id == self.acte_type_id
                )
                ord_ligne = ol[0] if ol else False
            nouvelles = [(0, 0, {
                'date': d, 'selected': True,
                'acte_type_id': self.acte_type_id.id,
                'ordonnance_ligne_id': ord_ligne.id if ord_ligne else False,
                'montant': montant_u, 'heure_acte': heure, 'warning': '',
            }) for d in dates]
        elif self.ordonnance_id:
            nouvelles = self._distribuer_dates_auto(dates, IrParam, heure)
        else:
            nouvelles = [(0, 0, {
                'date': d, 'selected': True,
                'acte_type_id': False, 'ordonnance_ligne_id': False,
                'montant': 0.0, 'heure_acte': heure, 'warning': _('Aucun acte assigné'),
            }) for d in dates]

        self.ligne_ids = [(5, 0, 0)] + nouvelles
        return self._reopen()

    def _distribuer_dates_auto(self, dates, IrParam, heure):
        lignes_ord = self.ordonnance_id.ligne_ids.sorted(
            lambda l: (l.acte_type_id.sequence or 0, l.id)
        ).filtered(lambda l: l.nb_seances_restantes > 0)
        if not lignes_ord:
            return [(0, 0, {
                'date': d, 'selected': False, 'acte_type_id': False,
                'ordonnance_ligne_id': False, 'montant': 0.0,
                'heure_acte': heure, 'warning': _('Séances épuisées'),
            }) for d in dates]
        remaining    = {l.id: l.nb_seances_restantes for l in lignes_ord}
        last_date    = {l.id: l.get_last_seance_date() for l in lignes_ord}
        montants     = {l.id: self._montant_unitaire(l.acte_type_id, IrParam) for l in lignes_ord}
        delai_global = self.delai_min_jours
        result = []
        for date in sorted(dates):
            assigned = False
            for ligne in lignes_ord:
                if remaining.get(ligne.id, 0) <= 0:
                    continue
                delai = max(ligne.acte_type_id.delai_min_jours or 0, delai_global)
                last  = last_date.get(ligne.id)
                if last and delai > 0 and (date - last).days < delai:
                    continue
                result.append((0, 0, {
                    'date': date, 'selected': True,
                    'acte_type_id': ligne.acte_type_id.id,
                    'ordonnance_ligne_id': ligne.id,
                    'montant': montants[ligne.id], 'heure_acte': heure, 'warning': '',
                }))
                remaining[ligne.id] -= 1
                last_date[ligne.id]  = date
                assigned = True
                break
            if not assigned:
                result.append((0, 0, {
                    'date': date, 'selected': False,
                    'acte_type_id': False, 'ordonnance_ligne_id': False,
                    'montant': 0.0, 'heure_acte': heure,
                    'warning': _('Non assignée : épuisé ou délai non respecté'),
                }))
        return result

    @staticmethod
    def _montant_unitaire(acte_type, IrParam):
        if not acte_type:
            return 0.0
        if acte_type.type_supplement == 'ifn':
            return float(IrParam.get_param('cps.supplement.ifn', 250))
        cfg = {
            'AMO': 'cps.tarif.amo', 'AMK': 'cps.tarif.amo', 'AMY': 'cps.tarif.amy',
            'AMI': 'cps.tarif.ami', 'AIS': 'cps.tarif.ami', 'DI':  'cps.tarif.ami',
            'AMS': 'cps.tarif.ams', 'AMP': 'cps.tarif.ams',
        }
        lk    = (acte_type.lettre_cle or '').upper()
        key   = cfg.get(lk)
        tarif = (float(IrParam.get_param(key, acte_type.tarif_unitaire or 490))
                 if key else (acte_type.tarif_unitaire or 490))
        return round(tarif * (acte_type.coefficient_defaut or 0), 0)

    # ── Application : création multi-feuilles ─────────────────────────────────

    def action_appliquer(self):
        self.ensure_one()
        sel = self.ligne_ids.filtered('selected').sorted('date')
        if not sel:
            raise UserError(_('Aucune date sélectionnée.'))

        today              = fields.Date.today()
        feuille_principale = self.feuille_id

        # Découpage en tranches de SEANCES_PAR_FEUILLE (16 lignes = formulaire FSA25)
        all_lignes = list(sel)
        chunks = [
            all_lignes[i:i + SEANCES_PAR_FEUILLE]
            for i in range(0, len(all_lignes), SEANCES_PAR_FEUILLE)
        ]

        feuilles_crees = []

        for idx, chunk in enumerate(chunks):
            if idx == 0:
                feuille = feuille_principale
            else:
                # Nouvelle feuille calquée sur la feuille principale
                last_date_chunk = max(l.date for l in chunk)
                feuille = self.env['cps.feuille.soins'].create({
                    'patient_id':            feuille_principale.patient_id.id,
                    'praticien_id':          feuille_principale.praticien_id.id,
                    'ordonnance_id':         feuille_principale.ordonnance_id.id or False,
                    'date_prescription':     feuille_principale.date_prescription,
                    'condition':             feuille_principale.condition,
                    'taux_remboursement':    feuille_principale.taux_remboursement,
                    'company_id':            feuille_principale.company_id.id,
                    'parcours_soins':        feuille_principale.parcours_soins,
                    'code_prescripteur':     feuille_principale.code_prescripteur,
                    'auxiliaire_remplacant': feuille_principale.auxiliaire_remplacant,
                    'accord_prealable':      feuille_principale.accord_prealable,
                    # date_feuille sera calculée automatiquement depuis date_fin_soins
                })
                feuilles_crees.append(feuille)

            # Ajout des actes dans cette feuille
            lignes_vals = [(0, 0, {
                'acte_type_id':        l.acte_type_id.id if l.acte_type_id else False,
                'date_acte':           l.date,
                'heure_acte':          l.heure_acte,
                'lettre_cle':          l.acte_type_id.lettre_cle if l.acte_type_id else False,
                'coefficient':         l.acte_type_id.coefficient_defaut if l.acte_type_id else 0,
                'ifd':                 self.ifd,
                'dimanche_ferie':      self.dimanche_ferie,
                'nuit':                self.nuit,
                'montant':             l.montant,
                'ordonnance_ligne_id': l.ordonnance_ligne_id.id if l.ordonnance_ligne_id else False,
            }) for l in chunk]
            feuille.write({'acte_ids': lignes_vals})

        # Message chatter sur la feuille principale
        msg = _(
            '%d séance(s) planifiée(s) répartie(s) sur %d feuille(s) FSA25.'
        ) % (len(sel), len(chunks))
        if feuilles_crees:
            noms = ', '.join(f.name for f in feuilles_crees)
            msg += _('\nFeuilles supplémentaires créées : %s') % noms
        feuille_principale.message_post(body=msg)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cps.feuille.soins',
            'res_id': feuille_principale.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_tout_selectionner(self):
        self.ligne_ids.write({'selected': True})
        return self._reopen()

    def action_tout_deselectionner(self):
        self.ligne_ids.write({'selected': False})
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


class WizardDateSelectionLigne(models.TransientModel):
    _name = 'cps.wizard.date.selection.ligne'
    _description = 'Ligne de date (wizard saisie séances)'
    _order = 'date, heure_acte'

    wizard_id           = fields.Many2one('cps.wizard.date.selection', required=True, ondelete='cascade')
    date                = fields.Date(required=True)
    selected            = fields.Boolean(string='✓', default=True)
    jour_semaine        = fields.Char(compute='_compute_jour', readonly=True)
    acte_type_id        = fields.Many2one('cps.acte.type', string='Acte')
    ordonnance_ligne_id = fields.Many2one('cps.ordonnance.ligne', readonly=True)
    montant             = fields.Float(digits=(10, 0))
    heure_acte          = fields.Float(
        string='Heure',
        default=8.0,
        digits=(2, 2),
        help='Heure de début de la séance (ex : 8.5 = 8h30).',
    )
    warning    = fields.Char(readonly=True)
    num_feuille = fields.Integer(
        compute='_compute_num_feuille',
        string='Feuille n°',
        help='Numéro prévisionnel de la feuille FSA25 (16 séances / feuille).',
    )

    @api.depends('date')
    def _compute_jour(self):
        j = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
        for rec in self:
            rec.jour_semaine = j[rec.date.weekday()] if rec.date else ''

    @api.depends('wizard_id.ligne_ids', 'wizard_id.ligne_ids.selected', 'selected', 'date')
    def _compute_num_feuille(self):
        # Grouper par wizard pour ne faire le calcul qu'une fois par wizard
        by_wizard = {}
        for rec in self:
            by_wizard.setdefault(rec.wizard_id.id, []).append(rec)

        for wizard_id, recs in by_wizard.items():
            if not wizard_id:
                for rec in recs:
                    rec.num_feuille = 0
                continue
            wizard = recs[0].wizard_id
            sel = wizard.ligne_ids.filtered('selected').sorted('date')
            sel_list = list(sel)
            idx_map  = {r.id: i for i, r in enumerate(sel_list)}
            for rec in recs:
                pos = idx_map.get(rec.id)
                rec.num_feuille = (pos // SEANCES_PAR_FEUILLE + 1) if pos is not None else 0

    @api.onchange('date')
    def _onchange_date_auto_assign(self):
        if not self.date or self.acte_type_id:
            return
        wizard = self.wizard_id
        if not wizard or not wizard.ordonnance_id:
            return
        IrParam = self.env['ir.config_parameter'].sudo()
        planned_counts = {}
        for l in wizard.ligne_ids:
            if l != self and l.selected and l.acte_type_id:
                aid = l.acte_type_id.id
                planned_counts[aid] = planned_counts.get(aid, 0) + 1
        lignes_ord = wizard.ordonnance_id.ligne_ids.sorted(
            lambda l: (l.acte_type_id.sequence or 0, l.id)
        ).filtered(lambda l: l.nb_seances_restantes > 0)
        for ligne_ord in lignes_ord:
            aid = ligne_ord.acte_type_id.id
            if planned_counts.get(aid, 0) < ligne_ord.nb_seances_restantes:
                self.acte_type_id        = ligne_ord.acte_type_id
                self.ordonnance_ligne_id = ligne_ord
                self.montant = WizardDateSelection._montant_unitaire(
                    ligne_ord.acte_type_id, IrParam
                )
                return

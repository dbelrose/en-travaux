import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WizardBordereau(models.TransientModel):
    _name = 'cps.wizard.bordereau'
    _description = 'Assistant de génération de bordereau mensuel'

    # ── Méthodes de valeurs par défaut ──────────────────────────────────────

    @api.model
    def _default_praticien(self):
        """Retourne le praticien lié à l'utilisateur connecté, ou False."""
        return self.env['cps.praticien'].search(
            [('user_id', '=', self.env.uid)], limit=1
        )

    @api.model
    def _earliest_confirmed_feuille(self, praticien):
        """
        Retourne la feuille confirmée sans bordereau ayant la date de prescription
        la plus ancienne pour le praticien donné.
        """
        if not praticien:
            return self.env['cps.feuille.soins']
        return self.env['cps.feuille.soins'].search([
            ('praticien_id', '=', praticien.id),
            ('state', '=', 'confirmed'),
            ('bordereau_id', '=', False),
            ('date_prescription', '!=', False),
        ], order='date_prescription asc', limit=1)

    @api.model
    def _default_mois(self):
        """
        Mois par défaut = mois de la feuille confirmée la plus ancienne
        sans bordereau pour le praticien connecté.
        Si aucune feuille n'est trouvée, retourne le mois courant.
        """
        praticien = self._default_praticien()
        feuille = self._earliest_confirmed_feuille(praticien)
        if feuille:
            return str(feuille.date_prescription.month).zfill(2)
        return str(datetime.date.today().month).zfill(2)

    @api.model
    def _default_annee(self):
        """
        Année par défaut = année de la feuille confirmée la plus ancienne
        sans bordereau pour le praticien connecté.
        Si aucune feuille n'est trouvée, retourne l'année courante.
        """
        praticien = self._default_praticien()
        feuille = self._earliest_confirmed_feuille(praticien)
        if feuille:
            return str(feuille.date_prescription.year)
        return str(datetime.date.today().year)

    @api.model
    def _default_feuilles(self):
        """
        Pré-charge toutes les feuilles confirmées sans bordereau du praticien
        connecté, de façon à ce que la liste soit déjà peuplée à l'ouverture
        du wizard (sans attendre un onchange).
        """
        praticien = self._default_praticien()
        if not praticien:
            return self.env['cps.feuille.soins']
        return self.env['cps.feuille.soins'].search([
            ('praticien_id', '=', praticien.id),
            ('state', '=', 'confirmed'),
            ('bordereau_id', '=', False),
        ])

    # ── Champs ──────────────────────────────────────────────────────────────

    praticien_id = fields.Many2one(
        'cps.praticien', string='Praticien', required=True,
        default=_default_praticien,
    )
    mois = fields.Selection([
        ('01', 'Janvier'), ('02', 'Février'), ('03', 'Mars'),
        ('04', 'Avril'), ('05', 'Mai'), ('06', 'Juin'),
        ('07', 'Juillet'), ('08', 'Août'), ('09', 'Septembre'),
        ('10', 'Octobre'), ('11', 'Novembre'), ('12', 'Décembre'),
    ], string='Mois', required=True, default=_default_mois)
    annee = fields.Char(
        string='Année', required=True, default=_default_annee,
    )
    feuille_ids = fields.Many2many(
        'cps.feuille.soins', string='Feuilles à inclure',
        domain="[('praticien_id','=',praticien_id),('state','=','confirmed'),('bordereau_id','=',False)]",
        default=_default_feuilles,
    )

    # ── Onchange ─────────────────────────────────────────────────────────────

    @api.onchange('praticien_id', 'mois', 'annee')
    def _onchange_load_feuilles(self):
        """Recharge les feuilles quand le praticien ou la période change."""
        if self.praticien_id and self.mois and self.annee:
            feuilles = self.env['cps.feuille.soins'].search([
                ('praticien_id', '=', self.praticien_id.id),
                ('state', '=', 'confirmed'),
                ('bordereau_id', '=', False),
            ])
            self.feuille_ids = feuilles

    # ── Action principale ────────────────────────────────────────────────────

    def action_generate(self):
        self.ensure_one()
        if not self.feuille_ids:
            raise UserError(_('Aucune feuille de soins sélectionnée.'))

        mois_labels = dict(self._fields['mois'].selection)
        mois_str = f"{mois_labels[self.mois]} {self.annee}"

        bordereau = self.env['cps.bordereau'].create({
            'praticien_id': self.praticien_id.id,
            'mois': mois_str,
            'date_bordereau': fields.Date.today(),
        })
        self.feuille_ids.write({'bordereau_id': bordereau.id})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Bordereau généré'),
            'res_model': 'cps.bordereau',
            'res_id': bordereau.id,
            'view_mode': 'form',
        }

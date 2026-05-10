from odoo import models, fields, api


class CpsPatientConfig(models.Model):
    """
    Données complémentaires CPS liées à un patient (res.partner).

    Ce modèle satellite évite d'ajouter des colonnes directement sur
    res_partner (table centrale d'Odoo). La relation est One2one :
    au plus un enregistrement par partenaire, créé à la demande.
    """
    _name = 'cps.patient.config'
    _description = 'Configuration patient CPS'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Patient',
        required=True, ondelete='cascade',
        index=True,
    )

    has_mutuelle = fields.Boolean(
        string='Mutuelle complémentaire',
        default=False,
        help="Cocher si le patient dispose d'une mutuelle prenant en charge "
             "la part restante après remboursement CPS.",
    )

    # ── Helpers ──────────────────────────────────────────────────────────────

    @api.model
    def _get_or_create(self, partner):
        """Retourne (en créant si besoin) la config CPS du partenaire."""
        config = self.search([('partner_id', '=', partner.id)], limit=1)
        if not config:
            config = self.create({'partner_id': partner.id})
        return config

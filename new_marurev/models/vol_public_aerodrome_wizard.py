from odoo import fields, models, api


class VolPublicAerodromeWizard(models.TransientModel):
    _name = 'manureva.vol_public_aerodrome_wizard'
    _description = 'Vols de transport aérien public – Aérodrome - Wizard'
    _inherit = ['multi.step.wizard.mixin']

    mouvement_id = fields.Many2one(
        comodel_name='manureva.seac',
        name="Mouvement",
        required=True,
        ondelete='cascade',
        default=lambda self: self._default_mouvement_id()
    )
    fc02 = fields.Many2one(
        'manureva.aerodrome',
        string='Aérodrome',
        help="Aérodrome source"
    )
    fc03 = fields.Many2one(
        'manureva.usager',
        string='Opérateur',
        help="Code du transporteur exploitant"
    )
    fc15 = fields.Selection(
        [['A', 'Arrivée'], ['D', 'Départ']],
        default='D',
        string='Mouvement',
        help="Mouvement départ/arrivée"
    )
    fc27 = fields.Many2one(
        'manureva.aeronef',
        string="Aéronef",
        domain="[('usager_id', '=?', fc03)]",
        help="Immatriculation de l'aéronef"
    )
    fc32 = fields.Date(
        string='Date bloc réelle'
    )
    fc33 = fields.Char(
        help='Heure bloc réelle, en heure locale (HH:MM)',
        string='Heure bloc réelle'
    )
    fc43 = fields.Selection(
        [('N', 'Balisage non en service'), ('S', 'Balisage en service')],
        default='N',
        string='Balisage'
    )

    @api.model
    def _selection_state(self):
        return [
            ('start', "Sélection d'un aérodrome"),
            ('operateur', "Sélection d'un opérateur"),
            ('mouvement', "Saisie d'un mouvement"),
            ('validation', 'Validation'),
            ('final', 'Validé'),
        ]

    @api.model
    def _default_mouvement_id(self):
        return self.env.context.get('active_id')

    def state_exit_start(self):
        self.state = 'operateur'

    def state_exit_operateur(self):
        self.state = 'mouvement'

    def state_exit_mouvement(self):
        self.state = 'validation'

    def state_exit_validation(self):
        for record in self:
            record.env['manureva.seac'].create({
                'aerodrome_id': record.fc02,
                'usager_id': record.fc03,
                'mouvement': record.fc15,
                'aeronef_id': record.fc27,
                'date': record.fc32,
                'heure_texte': record.fc33,
                'balisage': record.fc43
            })
        self.state = 'final'

    def state_previous_operateur(self):
        self.state = 'start'

    def state_previous_validation(self):
        self.state = 'mouvement'

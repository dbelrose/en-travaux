from odoo import fields, models


class VolPublicAerodrome(models.Model):
    _name = 'manureva.vol_public_aerodrome'
    _description = 'Vols de transport aérien public - Aérodrome'
    _order = 'write_date desc'

    name = fields.Char()

    fc02 = fields.Many2one(
        'manureva.aerodrome',
        string='Aérodrome source',
        help="Aérodrome source",
    )
    fc03 = fields.Many2one(
        'manureva.usager',
        string='Code du transporteur exploitant',
        help="Code du transporteur exploitant",
    )
    fc13 = fields.Char(
        string='Numéro de vol',
        group_operator='count',
        help="Numéro de vol",
    )
    fc14 = fields.Selection(
        [['D', 'Dérouté'], ['N', 'Non dérouté'], ['I', 'Interrompu']],
        default='N',
        string='Circonstance du vol',
        help="Circonstance du vol",
    )
    fc15 = fields.Selection(
        [['A', 'Arrivée'], ['D', 'Départ']],
        default='D',
        string='Mouvement départ/arrivée',
        help="Mouvement départ/arrivée",
    )
    fc16 = fields.Many2one(
        'manureva.aerodrome',
        string='Aérodrome de provenance/destination',
        help="Aérodrome de provenance/destination",
    )
    fc27 = fields.Many2one(
        'manureva.aeronef',
        string="Immatriculation de l'aéronef",
        domain="[('usager_id', '=?', fc03)]",
        help="Immatriculation de l'aéronef",
    )
    fc32 = fields.Date(
        string='Date bloc réelle',
    )
    fc33 = fields.Char(
        help='Heure bloc réelle, en heure locale (HH:MM:SS)',
        string='Heure bloc réelle',
    )
    fc34 = fields.Date(
        string='Date piste réelle',
    )
    fc35 = fields.Char(
        help='Heure piste réelle, en heure locale (HH:MM:SS)',
        string='Heure piste réelle',
    )
    fc42 = fields.Char(
        string='Piste utilisée',
        help="Piste utilisée",
    )
    fc43 = fields.Selection(
        [('N', 'Balisage non en service'), ('S', 'Balisage en service')],
        default='N',
        string='Balisage en service',
    )

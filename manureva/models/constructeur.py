from odoo import fields, models


class Constructeur (models.Model):
    _description = 'Constructeur'
    _inherits = {'res.partner': 'partner_id'}
    _name = 'manureva.constructeur'

    is_company = fields.Boolean(
        default=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        required=True,
        ondelete='restrict',
        auto_join=True,
        string='Constructeur',
        help='Informations de contact relatives au constructeur'
    )
    type_aeronef_ids = fields.One2many(
        comodel_name='manureva.type_aeronef',
        inverse_name='constructeur_id',
        string="Types d'aéronef",
        readonly=True,
    )

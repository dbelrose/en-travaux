# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Champ couleur pour le calendrier
    color = fields.Integer(
        string='Couleur',
        help='Couleur utilisée dans le calendrier des réservations (0-11)',
        default=0
    )
from odoo import models


class ResPartnerIdNumber(models.Model):
    _inherit = 'res.partner.id_number'

    _sql_constraints = [
        (
            'uniq_category_name',
            'unique(category_id, name)',
            "Un identifiant de même catégorie existe déjà."
        )
    ]

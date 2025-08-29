from odoo import models


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    # def action_view_purchase_orders(self):
    #     """Personnalise l'action pour injecter la devise par défaut"""
    #     self.ensure_one()
    #     return {
    #         'name': 'Request for Quotation',
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'purchase.order',
    #         'view_mode': 'form',
    #         'domain': [('requisition_id', '=', self.id)],
    #         'context': {
    #             'default_requisition_id': self.id,
    #             'default_currency_id': self.currency_id.id,
    #             'default_user_id': False,
    #         },
    #     }

    def copy_analytic_requisition_tags(self):
        for rec in self:
            if rec.line_ids:
                first_line_tags = rec.line_ids[0].analytic_tag_ids
                for line in rec.line_ids[1:]:
                    line.analytic_tag_ids = [(6, 0, first_line_tags.ids)]

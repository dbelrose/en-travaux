from odoo import models


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    def duplicate_requisition_line(self):
        for line in self:
            if line.requisition_id:
                line.copy({'requisition_id': line.requisition_id.id})

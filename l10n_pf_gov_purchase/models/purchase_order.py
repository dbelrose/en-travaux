from odoo import models, api, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    amount_total_company_currency = fields.Monetary(
        string="Total (XPF)",
        compute="_compute_amount_total_company_currency",
        currency_field='company_currency_id',
        store=True,
    )

    # READONLY_STATES = {
    #     'purchase': [('readonly', True)],
    #     'done': [('readonly', True)],
    #     'cancel': [('readonly', True)],
    # }

    # currency_id = fields.Many2one(
    #     'res.currency',
    #     string='Currency',
    #     required=True,
    #     states=READONLY_STATES)

    # @api.model
    # def default_get(self, fields_list):
    #     vals = super().default_get(fields_list)
    #
    #     requisition_id = self.env.context.get('default_requisition_id')
    #     if requisition_id:
    #         requisition = self.env['purchase.requisition'].browse(requisition_id)
    #         if requisition.currency_id:
    #             vals['currency_id'] = requisition.currency_id.id
    #
    #     return vals

    def copy_analytic_tags(self):
        for order in self:
            if order.order_line:
                first_line_tags = order.order_line[0].analytic_tag_ids
                for line in order.order_line[1:]:
                    line.analytic_tag_ids = [(6, 0, first_line_tags.ids)]

    @api.depends('amount_total', 'currency_id', 'date_order')
    def _compute_amount_total_company_currency(self):
        for order in self:
            if order.currency_id == order.company_id.currency_id:
                order.amount_total_company_currency = order.amount_total
            else:
                if order.currency_rate != 0.0:
                    order.amount_total_company_currency = order.amount_total / order.currency_rate
                else:
                    order.amount_total_company_currency = 0.0

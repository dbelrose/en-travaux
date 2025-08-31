from odoo import models, fields, api, _


class RentalOrderContract(models.Model):
    _inherit = 'rental.order.contract'

    customer_name = fields.Char(related='partner_id.name', string='Customer')
    date_start_text = fields.Char(string='Start Date', compute='_compute_date_start_text')
    date_end_text = fields.Char(string='End Date', compute='_compute_date_end_text')
    unit_price_text = fields.Char(string='Unit Price', compute='_compute_unit_price_text')
    product_description = fields.Char(related='product_id.name', string='Product')

    @api.depends('date_start')
    def _compute_date_start_text(self):
        for record in self:
            record.date_start_text = record.date_start.strftime('%d/%m/%Y')

    @api.depends('date_end')
    def _compute_date_end_text(self):
        for record in self:
            record.date_end_text = record.date_end.strftime('%d/%m/%Y')

    @api.depends('unit_price')
    def _compute_unit_price_text(self):
        for record in self:
            currency_symbol = record.company_id.currency_id.symbol
            formatted_price = '{:,.0f}'.format(record.unit_price).replace(',', ' ')
            record.unit_price_text = f"{formatted_price} {currency_symbol}"

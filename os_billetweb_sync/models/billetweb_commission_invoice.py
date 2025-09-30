from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class BilletwebCommissionInvoice(models.AbstractModel):
    _name = 'billetweb.commission.invoice'
    _description = 'Facturation automatique des commissions BilletWeb depuis les ventes'

    def generate_commission_invoices(self):
        today = fields.Date.today()
        _logger.info(f"[BilletWeb] Facturation des commissions à la date du {today}")

        companies = self.env['res.company'].search([])

        for company in companies:
            self = self.with_company(company)
            partner = company.partner_id
            pricelist = partner.property_product_pricelist

            details = self.env['billetweb.payout.detail'].search([
                ('commission_invoice_id', '=', False),
                ('payout_id.company_id', '=', company.id)
            ])

            if not details:
                continue

            product = self.env['product.product'].search([('default_code', '=', 'ACTBWB')], limit=1)
            if not product:
                raise ValueError("Produit 'Accompagnement BilletWeb' (ACTBWB) introuvable.")

            lines = []

            for line in details:
                net_amount = float(line.price or 0) - float(line.fees or 0)
                if net_amount > 0:
                    net_amount_xpf = round(net_amount * 1000 / 8.38, 0)
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'name': f"{product.name} / {line.ext_id} / {net_amount:.2f} EUR",
                        'quantity': 1,
                        'label': line.ext_id,
                        'price_unit': net_amount_xpf,
                        'currency_id': self.env.ref('base.EUR').id,
                    }))

            if not lines:
                continue

            invoice_client, invoice_supplier = self.env['invoice.helper'].create_intercompany_invoice(
                partner=partner,
                product=product,
                lines=lines,
                invoice_origin=f"Commission BilletWeb - {today.strftime('%Y-%m-%d')}",
                invoice_date=today,
            )

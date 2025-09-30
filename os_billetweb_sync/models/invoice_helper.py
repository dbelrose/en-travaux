from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.api import Environment

import logging

_logger = logging.getLogger(__name__)


class InvoiceHelper(models.AbstractModel):
    _name = 'invoice.helper'
    _description = 'Helper to create intercompany invoices'

    @api.model
    def create_intercompany_invoice(self, partner, product, lines, invoice_origin, invoice_date=None):
        if not partner or not partner.company_id:
            raise UserError(_("Le partenaire n'est pas lié à une société."))

        company_src = self.get_supplier_company(partner)
        _logger.info(f"[BilletWeb] create_intercompany_invoice.company_src={company_src}")

        company_dst = self.env['res.company'].search([('partner_id', '=', partner.id)], limit=1)
        _logger.info(f"[BilletWeb] create_intercompany_invoice.company_dst={company_dst}")

        invoice_date = invoice_date or fields.Date.context_today(self)

        # --- Construction lignes de facture (dans la société source)
        invoice_lines = []
        for line in lines:
            vals = line[2]  # Le dictionnaire des valeurs
            amount = float(vals['price_unit'] or 0)
            discount_percent = self.get_discount_percentage_from_pricelist(product, partner)
            if amount <= 0:
                continue
            invoice_lines.append((0, 0, {
                'product_id': product.id,
                'name': f"{product.name} / {vals['label'] or ''}",
                'quantity': 1,
                'price_unit': amount,
                'discount': discount_percent,
                'currency_id': company_src.currency_id.id,
            }))

        if not invoice_lines:
            raise UserError(_("Aucune ligne de facture valide."))

        # Créer la facture client dans la société du fournisseur
        invoice_client = self.env['account.move'].create({
            'company_id': company_src.id,
            'partner_id': partner.id,
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'currency_id': company_src.currency_id.id,
            'invoice_line_ids': invoice_lines,
            'invoice_origin': invoice_origin,
        })

        # --- Copier les lignes (adaptées) pour la société destinataire
        invoice_lines_dst = []
        for l in invoice_client.invoice_line_ids:
            invoice_lines_dst.append((0, 0, {
                'product_id': product.id,
                'name': l.name,
                'quantity': l.quantity,
                'price_unit': l.price_unit,
                'discount': l.discount,
                'currency_id': company_dst.currency_id.id,
            }))

        # Créer la facture fournisseur dans la société cliente
        invoice_supplier = self.env['account.move'].with_company(company_dst.id).sudo().create({
            'company_id': company_dst.id,
            'partner_id': company_src.partner_id.id,
            'move_type': 'in_invoice',
            'invoice_date': invoice_date,
            'currency_id': company_dst.currency_id.id,
            'invoice_line_ids': invoice_lines_dst,
            'invoice_origin': invoice_client.name,
        })

        return invoice_client, invoice_supplier

    def get_supplier_company(self, partner):
        # On cherche la relation où le partenaire est un client
        relation_type = self.env['res.partner.relation.type'].search([
            ('name', '=', 'Client')
        ], limit=1)
        _logger.info(f"[BilletWeb] get_supplier_company.relation_type={relation_type}")

        if not relation_type:
            return None

        relation = self.env['res.partner.relation'].search([
            ('left_partner_id', '=', partner.id),
            ('type_id', '=', relation_type.id)
        ], limit=1)
        _logger.info(f"[BilletWeb] get_supplier_company.relation={relation}")

        if relation and relation.right_partner_id:
            # On cherche une société associée à ce partenaire
            company = self.env['res.company'].search([
                ('partner_id', '=', relation.right_partner_id.id)
            ], limit=1)
            _logger.info(f"[BilletWeb] get_supplier_company.company={company}")

            return company

        return None

    def get_discount_percentage_from_pricelist(self, product, partner):
        price_list = partner.property_product_pricelist
        if not price_list:
            return 0.0

        # Recherche de la règle applicable au produit dans la liste de prix du partenaire
        item = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', price_list.id),
            ('compute_price', '=', 'percentage'),
            ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ], limit=1)

        if item:
            return item.percent_price

        return 0.0

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Plateformes activées
    hm_booking_enabled = fields.Boolean(string="Booking.com activé", default=True)
    hm_airbnb_enabled = fields.Boolean(
        string="Airbnb activé",
        default=lambda self: bool(
            self.env['ir.module.module'].sudo().search([
                ('name', '=', 'os_airbnb_pdf_importer'),
                ('state', '=', 'installed')
            ], limit=1)
        ),
        help="Si 'os_airbnb_pdf_importer' est installé, Airbnb est activé par défaut."
    )

    # Booking.com – factures optionnelles (ON par défaut)
    hm_booking_vendor_concierge_commission = fields.Boolean(
        string="Booking.com – Facture fournisseur commission concierge", default=True)
    hm_booking_vendor_platform_commission = fields.Boolean(
        string="Booking.com – Facture fournisseur commission plateforme", default=True)
    hm_booking_customer_concierge_commission = fields.Boolean(
        string="Booking.com – Facture client commission concierge", default=True)

    # Airbnb – factures optionnelles (OFF par défaut)
    hm_airbnb_vendor_concierge_commission = fields.Boolean(
        string="Airbnb – Facture fournisseur commission concierge", default=False)
    hm_airbnb_vendor_platform_commission = fields.Boolean(
        string="Airbnb – Facture fournisseur commission plateforme", default=False)
    hm_airbnb_customer_concierge_commission = fields.Boolean(
        string="Airbnb – Facture client commission concierge", default=False)

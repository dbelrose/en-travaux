# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Exposition des switches plateformes (company-aware via related)
    booking_enabled = fields.Boolean(
        string="Activer Booking.com",
        related='company_id.hm_booking_enabled', readonly=False)

    airbnb_enabled = fields.Boolean(
        string="Activer Airbnb",
        related='company_id.hm_airbnb_enabled', readonly=False)

    # Déclencheur d'installation du module import Airbnb PDF depuis Paramètres
    # Odoo exécutera l'install/uninstall lorsqu’on sauvegarde la page de réglages.
    module_os_airbnb_pdf_importer = fields.Boolean(
        string="Installer le connecteur Airbnb PDF (os_airbnb_pdf_importer)")

    # Booking.com – factures optionnelles
    booking_vendor_concierge_commission = fields.Boolean(
        string="Facture fournisseur commission concierge",
        related='company_id.hm_booking_vendor_concierge_commission', readonly=False)

    booking_vendor_platform_commission = fields.Boolean(
        string="Facture fournisseur commission plateforme",
        related='company_id.hm_booking_vendor_platform_commission', readonly=False)

    booking_customer_concierge_commission = fields.Boolean(
        string="Facture client commission concierge",
        related='company_id.hm_booking_customer_concierge_commission', readonly=False)

    # Airbnb – factures optionnelles
    airbnb_vendor_concierge_commission = fields.Boolean(
        string="Facture fournisseur commission concierge",
        related='company_id.hm_airbnb_vendor_concierge_commission', readonly=False)

    airbnb_vendor_platform_commission = fields.Boolean(
        string="Facture fournisseur commission plateforme",
        related='company_id.hm_airbnb_vendor_platform_commission', readonly=False)

    airbnb_customer_concierge_commission = fields.Boolean(
        string="Facture client commission concierge",
        related='company_id.hm_airbnb_customer_concierge_commission', readonly=False)

    # Synchronisation simple : cocher "Airbnb activé" coche le module ; et inversement.
    @api.onchange('airbnb_enabled')
    def _onchange_airbnb_enabled(self):
        if self.airbnb_enabled:
            self.module_os_airbnb_pdf_importer = True  # déclenche installation
    @api.onchange('module_os_airbnb_pdf_importer')
    def _onchange_module_airbnb(self):
        if self.module_os_airbnb_pdf_importer:
            self.airbnb_enabled = True  # si déjà installé, on reflète l’activation

    # Rien à surcharger dans set_values/get_values car on utilise des related company_id.*
    # L’installation des "module_*" est gérée par res.config.settings.execute() d’Odoo.

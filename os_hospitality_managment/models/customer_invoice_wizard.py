# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CustomerInvoiceConfigWizard(models.TransientModel):
    _name = 'customer.invoice.config.wizard'
    _description = 'Assistant de configuration des factures clients'

    # Configuration des produits
    accommodation_product_id = fields.Many2one(
        'product.product', 
        string='Produit Hébergement',
        domain=[('type', '=', 'service'), ('sale_ok', '=', True)],
        help="Produit utilisé pour facturer l'hébergement aux clients"
    )
    
    accommodation_price = fields.Float(
        string='Prix hébergement (XPF)', 
        default=10000.0,
        help="Prix par défaut pour une nuit d'hébergement"
    )
    
    tax_product_id = fields.Many2one(
        'product.product', 
        string='Produit Taxe de séjour',
        domain=[('type', '=', 'service'), ('sale_ok', '=', True)],
        help="Produit utilisé pour facturer la taxe de séjour aux clients"
    )
    
    tax_price = fields.Float(
        string='Prix taxe séjour (XPF/nuitée)', 
        default=60.0,
        help="Prix de la taxe de séjour par nuitée adulte"
    )

    # Options de facturation
    group_by_customer = fields.Boolean(
        string='Grouper par client', 
        default=True,
        help="Si coché, toutes les réservations d'un même client sur le mois seront sur une seule facture"
    )
    
    include_tax_on_invoice = fields.Boolean(
        string='Inclure taxe de séjour', 
        default=True,
        help="Si coché, la taxe de séjour sera ajoutée aux factures clients"
    )
    
    auto_validate_invoices = fields.Boolean(
        string='Valider automatiquement', 
        default=False,
        help="Si coché, les factures créées seront automatiquement validées"
    )

    # Informations de prévisualisation
    booking_month_id = fields.Many2one(
        'booking.month', 
        string='Mois à traiter',
        help="Mois pour lequel configurer la génération de factures"
    )
    
    preview_customer_count = fields.Integer(
        string='Nombre de clients', 
        compute='_compute_preview',
        help="Nombre estimé de factures clients qui seront créées"
    )
    
    preview_total_amount = fields.Monetary(
        string='Montant total estimé', 
        compute='_compute_preview',
        currency_field='company_currency_id'
    )
    
    company_currency_id = fields.Many2one(
        'res.currency', 
        related='company_id.currency_id'
    )
    
    company_id = fields.Many2one(
        'res.company', 
        default=lambda self: self.env.company
    )

    @api.depends('booking_month_id', 'accommodation_price', 'tax_price', 'include_tax_on_invoice')
    def _compute_preview(self):
        for wizard in self:
            if not wizard.booking_month_id:
                wizard.preview_customer_count = 0
                wizard.preview_total_amount = 0
                continue
                
            # Récupérer les réservations du mois
            reservations = self.env['booking.import.line'].search([
                ('property_type_id', '=', wizard.booking_month_id.property_type_id.id),
                ('arrival_date', '>=', wizard.booking_month_id.period_start),
                ('arrival_date', '<=', wizard.booking_month_id.period_end),
                ('status', '=', 'ok'),
            ])
            
            if wizard.group_by_customer:
                wizard.preview_customer_count = len(reservations.mapped('partner_id'))
            else:
                wizard.preview_customer_count = len(reservations)
            
            # Calcul du montant estimé
            total_amount = 0
            for reservation in reservations:
                # Hébergement
                total_amount += wizard.accommodation_price * reservation.duration_nights
                
                # Taxe de séjour
                if wizard.include_tax_on_invoice:
                    total_amount += wizard.tax_price * reservation.nights_adults
            
            wizard.preview_total_amount = total_amount

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        
        # Si on vient d'un mois spécifique
        if self.env.context.get('active_model') == 'booking.month':
            res['booking_month_id'] = self.env.context.get('active_id')
        
        # Essayer de récupérer les produits existants
        accommodation_product = self.env['product.product'].search([
            ('name', 'ilike', 'Hébergement'),
            ('type', '=', 'service'),
            ('sale_ok', '=', True)
        ], limit=1)
        
        if accommodation_product:
            res['accommodation_product_id'] = accommodation_product.id
            res['accommodation_price'] = accommodation_product.list_price
        
        tax_product = self.env['product.product'].search([
            ('name', 'ilike', 'Taxe de séjour'),
            ('type', '=', 'service'), 
            ('sale_ok', '=', True)
        ], limit=1)
        
        if tax_product:
            res['tax_product_id'] = tax_product.id
            res['tax_price'] = tax_product.list_price
            
        return res

    def action_create_products(self):
        """Crée les produits nécessaires pour la facturation client"""
        self.ensure_one()
        
        # Créer ou mettre à jour le produit hébergement
        if not self.accommodation_product_id:
            self.accommodation_product_id = self.env['product.product'].create({
                'name': 'Hébergement touristique',
                'type': 'service',
                'sale_ok': True,
                'purchase_ok': False,
                'list_price': self.accommodation_price,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                'categ_id': self.env.ref('product.product_category_all').id,
            })
        else:
            self.accommodation_product_id.list_price = self.accommodation_price
            
        # Créer ou mettre à jour le produit taxe
        if self.include_tax_on_invoice and not self.tax_product_id:
            self.tax_product_id = self.env['product.product'].create({
                'name': 'Taxe de séjour',
                'type': 'service',
                'sale_ok': True, 
                'purchase_ok': False,
                'list_price': self.tax_price,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                'categ_id': self.env.ref('product.product_category_all').id,
            })
        elif self.include_tax_on_invoice and self.tax_product_id:
            self.tax_product_id.list_price = self.tax_price
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': 'Produits créés/mis à jour avec succès',
                'type': 'success'
            }
        }

    def action_generate_invoices(self):
        """Génère les factures clients avec la configuration choisie"""
        self.ensure_one()
        
        if not self.booking_month_id:
            raise UserError("Veuillez sélectionner un mois à traiter.")
        
        if self.booking_month_id.customer_invoices_generated:
            raise UserError("Les factures clients ont déjà été générées pour ce mois.")
        
        # Créer les produits si nécessaire
        self.action_create_products()
        
        # Configurer temporairement les options sur le mois
        month = self.booking_month_id
        
        try:
            # Sauvegarder la configuration dans le contexte
            month = month.with_context(
                customer_invoice_config={
                    'accommodation_product_id': self.accommodation_product_id.id,
                    'tax_product_id': self.tax_product_id.id if self.include_tax_on_invoice else False,
                    'group_by_customer': self.group_by_customer,
                    'auto_validate': self.auto_validate_invoices,
                }
            )
            
            # Générer les factures
            result = month.action_generate_customer_invoices()
            
            # Post-traitement : validation automatique si demandée
            if self.auto_validate_invoices:
                invoices = month.customer_invoice_ids.filtered(lambda inv: inv.state == 'draft')
                if invoices:
                    invoices.action_post()
                    
            return result
            
        except Exception as e:
            raise UserError(f"Erreur lors de la génération : {str(e)}")

    def action_preview_invoices(self):
        """Prévisualise les factures qui seront créées"""
        self.ensure_one()
        
        if not self.booking_month_id:
            raise UserError("Veuillez sélectionner un mois à traiter.")
        
        # Récupérer les réservations
        reservations = self.env['booking.import.line'].search([
            ('property_type_id', '=', self.booking_month_id.property_type_id.id),
            ('arrival_date', '>=', self.booking_month_id.period_start),
            ('arrival_date', '<=', self.booking_month_id.period_end),
            ('status', '=', 'ok'),
        ])
        
        if not reservations:
            raise UserError("Aucune réservation trouvée pour ce mois.")
        
        # Préparer les données de prévisualisation
        preview_data = []
        
        if self.group_by_customer:
            customers = reservations.mapped('partner_id')
            for customer in customers:
                customer_reservations = reservations.filtered(lambda r: r.partner_id == customer)
                
                total_accommodation = sum(r.duration_nights for r in customer_reservations) * self.accommodation_price
                total_tax = sum(r.nights_adults for r in customer_reservations) * self.tax_price if self.include_tax_on_invoice else 0
                
                preview_data.append({
                    'customer': customer.name,
                    'reservations_count': len(customer_reservations),
                    'accommodation_amount': total_accommodation,
                    'tax_amount': total_tax,
                    'total_amount': total_accommodation + total_tax,
                })
        else:
            for reservation in reservations:
                total_accommodation = reservation.duration_nights * self.accommodation_price
                total_tax = reservation.nights_adults * self.tax_price if self.include_tax_on_invoice else 0
                
                preview_data.append({
                    'customer': reservation.partner_id.name,
                    'reservations_count': 1,
                    'accommodation_amount': total_accommodation, 
                    'tax_amount': total_tax,
                    'total_amount': total_accommodation + total_tax,
                })
        
        # Créer un message de prévisualisation
        message = f"Prévisualisation pour {self.booking_month_id.display_name}:\n\n"
        message += f"• {len(preview_data)} facture(s) client(s) seront créées\n"
        message += f"• Montant total: {sum(item['total_amount'] for item in preview_data):,.0f} XPF\n\n"
        
        message += "Détail par client:\n"
        for item in preview_data[:10]:  # Limiter à 10 pour l'affichage
            message += f"- {item['customer']}: {item['total_amount']:,.0f} XPF "
            message += f"({item['reservations_count']} rés.)\n"
        
        if len(preview_data) > 10:
            message += f"... et {len(preview_data) - 10} autres clients"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'info',
                'sticky': True
            }
        }
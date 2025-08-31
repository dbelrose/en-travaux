# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class HospitalityConfigWizard(models.TransientModel):
    _name = 'hospitality.config.wizard'
    _description = 'Assistant de configuration des tarifs Hospitality'

    # Tarifs à configurer
    tourist_tax_rate = fields.Float(
        string='Tarif taxe de séjour',
        default=60.0,
        required=True,
        help='Montant en XPF par nuitée adulte'
    )

    concierge_commission_rate = fields.Float(
        string='Taux commission conciergerie',
        default=20.0,
        required=True,
        help='Pourcentage appliqué sur le montant net (CA - Commission Booking - Taxe séjour)'
    )

    # Période d'application
    date_start = fields.Date(
        string='Date de début',
        default=fields.Date.context_today,
        help='Date à partir de laquelle les nouveaux tarifs s\'appliquent'
    )

    date_end = fields.Date(
        string='Date de fin',
        help='Date de fin d\'application des tarifs (optionnel)'
    )

    # Options
    update_existing = fields.Boolean(
        string='Mettre à jour les règles existantes',
        default=True,
        help='Si coché, les règles existantes seront mises à jour. Sinon, de nouvelles règles seront créées.'
    )

    @api.model
    def default_get(self, fields_list):
        """Récupère les valeurs actuelles des tarifs"""
        res = super().default_get(fields_list)

        # Récupérer le tarif actuel de la taxe de séjour
        tourist_tax_product = self.env['product.product'].search([
            ('default_code', '=', 'TAXE_SEJOUR')
        ], limit=1)

        if tourist_tax_product:
            municipality_pricelist = self.env['product.pricelist'].search([
                ('name', '=', 'Tarifs Municipalité')
            ], limit=1)

            if municipality_pricelist:
                price = tourist_tax_product._get_price_in_pricelist(municipality_pricelist)
                if price:
                    res['tourist_tax_rate'] = price

        # Récupérer le taux actuel de commission conciergerie
        concierge_product = self.env['product.product'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE')
        ], limit=1)

        if concierge_product:
            concierge_pricelist = self.env['product.pricelist'].search([
                ('name', '=', 'Tarifs Conciergerie')
            ], limit=1)

            if concierge_pricelist:
                rate = concierge_product._get_price_in_pricelist(concierge_pricelist)
                if rate:
                    res['concierge_commission_rate'] = rate

        return res

    def action_apply_configuration(self):
        """Applique la configuration des tarifs"""
        self.ensure_one()

        # Validation
        if self.tourist_tax_rate <= 0:
            raise ValueError("Le tarif de la taxe de séjour doit être supérieur à 0")

        if self.concierge_commission_rate <= 0 or self.concierge_commission_rate > 100:
            raise ValueError("Le taux de commission doit être entre 0 et 100%")

        if self.date_end and self.date_end < self.date_start:
            raise ValueError("La date de fin doit être postérieure à la date de début")

        messages = []

        # 1. Configurer la taxe de séjour
        tourist_tax_result = self._configure_tourist_tax()
        messages.append(tourist_tax_result)

        # 2. Configurer la commission conciergerie
        concierge_result = self._configure_concierge_commission()
        messages.append(concierge_result)

        # 3. Mettre à jour les produits par défaut si nécessaire
        self._update_default_prices()

        # 4. Forcer le recalcul des vues mensuelles en cours
        self._refresh_monthly_views()

        # Message de confirmation
        message = "Configuration appliquée avec succès:\n" + "\n".join(messages)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Configuration terminée',
                'message': message,
                'type': 'success',
            }
        }

    def _configure_tourist_tax(self):
        """Configure le tarif de la taxe de séjour"""
        # Rechercher la liste de prix municipalité
        municipality_pricelist = self.env['product.pricelist'].search([
            ('name', '=', 'Tarifs Municipalité')
        ], limit=1)

        if not municipality_pricelist:
            raise ValueError("Liste de prix 'Tarifs Municipalité' introuvable!")

        # Rechercher le produit taxe de séjour
        tourist_tax_product = self.env['product.template'].search([
            ('default_code', '=', 'TAXE_SEJOUR')
        ], limit=1)

        if not tourist_tax_product:
            raise ValueError("Produit 'Taxe de séjour' introuvable!")

        # Rechercher ou créer la règle de prix
        pricelist_item = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', municipality_pricelist.id),
            ('product_tmpl_id', '=', tourist_tax_product.id),
            ('applied_on', '=', '1_product')
        ], limit=1)

        vals = {
            'pricelist_id': municipality_pricelist.id,
            'product_tmpl_id': tourist_tax_product.id,
            'applied_on': '1_product',
            'compute_price': 'fixed',
            'fixed_price': self.tourist_tax_rate,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'min_quantity': 1
        }

        if pricelist_item and self.update_existing:
            pricelist_item.write(vals)
            action = "mis à jour"
        else:
            if pricelist_item:
                # Terminer l'ancienne règle
                pricelist_item.write({'date_end': self.date_start})
            self.env['product.pricelist.item'].create(vals)
            action = "créé"

        return f"• Tarif taxe de séjour {action}: {self.tourist_tax_rate} XPF/nuitée"

    def _configure_concierge_commission(self):
        """Configure le taux de commission conciergerie"""
        # Rechercher la liste de prix conciergerie
        concierge_pricelist = self.env['product.pricelist'].search([
            ('name', '=', 'Tarifs Conciergerie')
        ], limit=1)

        if not concierge_pricelist:
            raise ValueError("Liste de prix 'Tarifs Conciergerie' introuvable!")

        # Rechercher le produit commission conciergerie
        concierge_product = self.env['product.template'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE')
        ], limit=1)

        if not concierge_product:
            raise ValueError("Produit 'Commission conciergerie' introuvable!")

        # Rechercher ou créer la règle de prix
        pricelist_item = self.env['product.pricelist.item'].search([
            ('pricelist_id', '=', concierge_pricelist.id),
            ('product_tmpl_id', '=', concierge_product.id),
            ('applied_on', '=', '1_product')
        ], limit=1)

        vals = {
            'pricelist_id': concierge_pricelist.id,
            'product_tmpl_id': concierge_product.id,
            'applied_on': '1_product',
            'compute_price': 'fixed',
            'fixed_price': self.concierge_commission_rate,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'min_quantity': 1
        }

        if pricelist_item and self.update_existing:
            pricelist_item.write(vals)
            action = "mis à jour"
        else:
            if pricelist_item:
                # Terminer l'ancienne règle
                pricelist_item.write({'date_end': self.date_start})
            self.env['product.pricelist.item'].create(vals)
            action = "créé"

        return f"• Taux commission conciergerie {action}: {self.concierge_commission_rate}%"

    def _update_default_prices(self):
        """Met à jour les prix par défaut des produits"""
        # Mettre à jour le produit taxe de séjour
        tourist_tax_product = self.env['product.template'].search([
            ('default_code', '=', 'TAXE_SEJOUR')
        ], limit=1)
        if tourist_tax_product:
            tourist_tax_product.write({
                'list_price': self.tourist_tax_rate,
                'standard_price': self.tourist_tax_rate
            })

        # Mettre à jour le produit commission conciergerie
        concierge_product = self.env['product.template'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE')
        ], limit=1)
        if concierge_product:
            concierge_product.write({
                'list_price': self.concierge_commission_rate,
                'standard_price': self.concierge_commission_rate
            })

    def _refresh_monthly_views(self):
        """Force le recalcul des vues mensuelles en cours"""
        # Recalculer les vues du mois en cours et des 2 derniers mois
        current_date = fields.Date.context_today(self)

        monthly_views = self.env['booking.month'].search([
            ('year', '>=', current_date.year - 1),  # Dernière année
            ('month', '>=', max(1, current_date.month - 2))  # 3 derniers mois
        ])

        for view in monthly_views:
            try:
                view.action_recalculate()
            except Exception as e:
                _logger.warning(f"Impossible de recalculer la vue {view.display_name}: {str(e)}")

        # Recalculer les déclarations trimestrielles de l'année en cours
        quarterly_views = self.env['booking.quarter'].search([
            ('year', '=', current_date.year)
        ])

        for view in quarterly_views:
            try:
                view.action_recalculate()
            except Exception as e:
                _logger.warning(f"Impossible de recalculer la déclaration {view.display_name}: {str(e)}")

    def action_preview_changes(self):
        """Prévisualise les changements sans les appliquer"""
        self.ensure_one()

        preview_lines = []

        # Prévisualisation taxe de séjour
        current_tax_rate = self._get_current_tourist_tax_rate()
        if current_tax_rate != self.tourist_tax_rate:
            preview_lines.append(
                f"Taxe de séjour: {current_tax_rate} → {self.tourist_tax_rate} XPF/nuitée"
            )
        else:
            preview_lines.append(f"Taxe de séjour: {self.tourist_tax_rate} XPF/nuitée (inchangé)")

        # Prévisualisation commission conciergerie
        current_commission_rate = self._get_current_concierge_rate()
        if current_commission_rate != self.concierge_commission_rate:
            preview_lines.append(
                f"Commission conciergerie: {current_commission_rate}% → {self.concierge_commission_rate}%"
            )
        else:
            preview_lines.append(f"Commission conciergerie: {self.concierge_commission_rate}% (inchangé)")

        # Période d'application
        period_text = f"À partir du {self.date_start}"
        if self.date_end:
            period_text += f" jusqu'au {self.date_end}"
        preview_lines.append(period_text)

        message = "Aperçu des modifications:\n\n" + "\n".join(f"• {line}" for line in preview_lines)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Aperçu des modifications',
                'message': message,
                'type': 'info',
            }
        }

    def _get_current_tourist_tax_rate(self):
        """Récupère le tarif actuel de la taxe de séjour"""
        tourist_tax_product = self.env['product.product'].search([
            ('default_code', '=', 'TAXE_SEJOUR')
        ], limit=1)

        if tourist_tax_product:
            municipality_pricelist = self.env['product.pricelist'].search([
                ('name', '=', 'Tarifs Municipalité')
            ], limit=1)

            if municipality_pricelist:
                return tourist_tax_product._get_price_in_pricelist(municipality_pricelist)

        return 60.0  # Valeur par défaut

    def _get_current_concierge_rate(self):
        """Récupère le taux actuel de commission conciergerie"""
        concierge_product = self.env['product.product'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE')
        ], limit=1)

        if concierge_product:
            concierge_pricelist = self.env['product.pricelist'].search([
                ('name', '=', 'Tarifs Conciergerie')
            ], limit=1)

            if concierge_pricelist:
                return concierge_product._get_price_in_pricelist(concierge_pricelist)

        return 20.0  # Valeur par défaut


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_view_pricelist_rules(self):
        """Action pour voir les règles de prix de ce produit"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Règles de prix - {self.name}',
            'res_model': 'product.pricelist.item',
            'view_mode': 'tree,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {
                'default_product_tmpl_id': self.id,
                'default_applied_on': '1_product',
                'default_compute_price': 'fixed'
            }
        }


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    def action_view_pricelist_items(self):
        """Action pour voir les éléments de cette liste de prix"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Éléments - {self.name}',
            'res_model': 'product.pricelist.item',
            'view_mode': 'tree,form',
            'domain': [('pricelist_id', '=', self.id)],
            'context': {
                'default_pricelist_id': self.id,
                'default_applied_on': '1_product',
                'default_compute_price': 'fixed'
            }
        }

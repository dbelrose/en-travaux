# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class BookingImportLine(models.Model):
    _name = 'booking.import.line'
    _description = 'Ligne d\'importation Booking.com'
    _order = 'arrival_date desc, id desc'

    # Relation avec l'import parent
    import_id = fields.Many2one('booking.import', string='Import', required=True, ondelete='cascade')
    
    # Informations client
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    booker_id = fields.Many2one('res.partner', string='Réservateur')
    
    # Informations propriété
    property_type_id = fields.Many2one('product.template', string='Type d\'hébergement', required=True)
    
    # Informations séjour
    arrival_date = fields.Date(string='Date d\'arrivée', required=True)
    duration_nights = fields.Integer(string='Durée (nuits)', required=True, default=1)
    pax_nb = fields.Integer(string='Nombre de personnes', required=True, default=1)
    children = fields.Integer(string='Nombre d\'enfants (≤12 ans)', default=0)
    
    # Statuts
    payment_status = fields.Selection([
        ('Entièrement payée', 'Entièrement payée'),
        ('Partiellement payée', 'Partiellement payée'),
        ('Non payée', 'Non payée'),
        ('Remboursée', 'Remboursée'),
    ], string='Statut paiement', default='Entièrement payée')
    
    status = fields.Selection([
        ('ok', 'OK'),  # Pour compatibilité avec l'import
        ('Annulé', 'Annulé'),
        ('No-show', 'No-show'),
        ('Modifié', 'Modifié'),
    ], string='Statut', default='ok')
    
    # Informations financières
    rate = fields.Float(string='Tarif (XPF)', digits='Product Price')
    commission_amount = fields.Float(string='Commission (XPF)', digits='Product Price')
    
    # Champs calculés
    nights_adults = fields.Integer(string='Nuitées adultes', compute='_compute_nights_adults', store=True)
    nights_children = fields.Integer(string='Nuitées enfants', compute='_compute_nights_children', store=True)
    tax_amount = fields.Float(string='Montant taxe (XPF)', compute='_compute_tax_amount', store=True)
    
    @api.depends('duration_nights', 'pax_nb', 'children')
    def _compute_nights_adults(self):
        """Calcule le nombre de nuitées pour les adultes"""
        for record in self:
            adults = (record.pax_nb or 0) - (record.children or 0)
            record.nights_adults = (record.duration_nights or 0) * max(adults, 0)
    
    @api.depends('duration_nights', 'children')
    def _compute_nights_children(self):
        """Calcule le nombre de nuitées pour les enfants"""
        for record in self:
            record.nights_children = (record.duration_nights or 0) * (record.children or 0)
    
    @api.depends('nights_adults')
    def _compute_tax_amount(self):
        """Calcule le montant de la taxe de séjour (60 XPF par nuitée adulte)"""
        for record in self:
            record.tax_amount = record.nights_adults * 60.0
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Met à jour le booker par défaut quand le client change"""
        if self.partner_id and not self.booker_id:
            self.booker_id = self.partner_id
    
    @api.onchange('import_id')
    def _onchange_import_id(self):
        """Met à jour le type de propriété depuis l'import"""
        if self.import_id and self.import_id.property_type_id:
            self.property_type_id = self.import_id.property_type_id
    
    def name_get(self):
        """Retourne un nom lisible pour les lignes"""
        result = []
        for record in self:
            name = f"{record.partner_id.name} - {record.arrival_date}"
            if record.property_type_id:
                name += f" ({record.property_type_id.name})"
            result.append((record.id, name))
        return result
    
    @api.model
    def create(self, vals):
        """Surcharge create pour validation"""
        # S'assurer que le property_type_id correspond à celui de l'import
        if 'import_id' in vals and vals['import_id'] and not vals.get('property_type_id'):
            import_record = self.env['booking.import'].browse(vals['import_id'])
            if import_record.property_type_id:
                vals['property_type_id'] = import_record.property_type_id.id
        
        return super().create(vals)
    
    def write(self, vals):
        """Surcharge write pour validation"""
        # Empêcher de changer le property_type_id s'il ne correspond pas à l'import
        if 'property_type_id' in vals:
            for record in self:
                if record.import_id.property_type_id and vals['property_type_id'] != record.import_id.property_type_id.id:
                    vals.pop('property_type_id')  # Retirer la modification
                    _logger.warning(f"Tentative de modification du type de propriété non autorisée sur la ligne {record.id}")
        
        return super().write(vals)
    
    def action_edit_reservation(self):
        """Action pour modifier une réservation via le wizard"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Modifier la réservation',
            'res_model': 'booking.import.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_import_id': self.import_id.id,
                'default_partner_id': self.partner_id.id,
                'default_booker_id': self.booker_id.id,
                'default_arrival_date': self.arrival_date,
                'default_duration_nights': self.duration_nights,
                'default_pax_nb': self.pax_nb,
                'default_children': self.children,
                'default_payment_status': self.payment_status,
                'default_status': self.status,
                'default_rate': self.rate,
                'default_commission_amount': self.commission_amount,
                'line_to_edit': self.id,
            }
        }
    
    def action_duplicate_reservation(self):
        """Action pour dupliquer une réservation"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Dupliquer la réservation',
            'res_model': 'booking.import.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_import_id': self.import_id.id,
                'default_partner_id': self.partner_id.id,
                'default_booker_id': self.booker_id.id,
                'default_arrival_date': self.arrival_date,
                'default_duration_nights': self.duration_nights,
                'default_pax_nb': self.pax_nb,
                'default_children': self.children,
                'default_payment_status': self.payment_status,
                'default_status': self.status,
                'default_rate': self.rate,
                'default_commission_amount': self.commission_amount,
            }
        }

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)


class BookingManualWizard(models.TransientModel):
    _name = 'booking.manual.wizard'
    _description = 'Assistant de saisie manuelle Booking'

    # Sélection de la période et propriété
    year = fields.Integer(string='Année', required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection(
        selection=[(str(i), datetime(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mois',
        store=True,
    )
    # month = fields.Selection(
    #     selection=[(str(i), fields.Date(1900, i, 1).strftime('%B')) for i in range(1, 13)],
    #     string='Mois',
    #     required=True,
    #     default=lambda self: str(fields.Date.today().month)
    # )
    property_type_id = fields.Many2one(
        'product.template', 
        string='Type d\'hébergement',
        required=True,
        domain="[('purchase_ok', '=', False)]"
    )
    
    # État du wizard
    state = fields.Selection([
        ('select', 'Sélection période/propriété'),
        ('edit', 'Saisie des réservations')
    ], default='select', string='Étape')
    
    # Import record créé
    import_id = fields.Many2one('booking.import', string='Import créé')
    
    def action_create_import(self):
        """Crée un nouvel enregistrement d'import pour saisie manuelle"""
        self.ensure_one()
        
        # Vérifier si un import existe déjà pour cette période/propriété
        existing_import = self.env['booking.import'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('property_type_id', '=', self.property_type_id.id)
        ], limit=1)
        
        if existing_import:
            # Utiliser l'import existant
            self.import_id = existing_import
            return self._open_import_form()
        else:
            # Créer un nouvel import
            new_import = self.env['booking.import'].create({
                'year': self.year,
                'month': self.month,
                'property_type_id': self.property_type_id.id,
                'import_date': fields.Datetime.now(),
                'company_id': self.env.user.company_id.id,
            })
            self.import_id = new_import
            return self._open_import_form()
    
    def _open_import_form(self):
        """Ouvre le formulaire d'import pour saisie"""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Saisie manuelle - {self.property_type_id.name} ({self.month}/{self.year})',
            'res_model': 'booking.import',
            'view_mode': 'form',
            'res_id': self.import_id.id,
            'target': 'current',
            'context': {
                'default_year': self.year,
                'default_month': self.month,
                'default_property_type_id': self.property_type_id.id,
                'manual_entry_mode': True,
            }
        }
    
    def action_cancel(self):
        """Annule le wizard"""
        return {'type': 'ir.actions.act_window_close'}


class BookingImportLineWizard(models.TransientModel):
    _name = 'booking.import.line.wizard'
    _description = 'Assistant pour ajouter/modifier une ligne de réservation'
    
    import_id = fields.Many2one('booking.import', string='Import', required=True)
    line_to_edit = fields.Many2one('booking.import.line', string='Ligne à modifier')
    
    # Informations client
    partner_id = fields.Many2one('res.partner', string='Client', required=True)
    booker_id = fields.Many2one('res.partner', string='Réservateur')
    create_new_partner = fields.Boolean(string='Créer un nouveau client')
    partner_name = fields.Char(string='Nom du client')
    partner_phone = fields.Char(string='Téléphone')
    partner_country_id = fields.Many2one('res.country', string='Pays')
    
    # Informations séjour
    arrival_date = fields.Date(string='Date d\'arrivée', required=True)
    duration_nights = fields.Integer(string='Durée (nuits)', required=True, default=1)
    pax_nb = fields.Integer(string='Nombre de personnes', required=True, default=1)
    children = fields.Integer(string='Nombre d\'enfants (≤12 ans)', default=0)
    
    # Informations booking
    payment_status = fields.Selection([
        ('Entièrement payée', 'Entièrement payée'),
        ('Partiellement payée', 'Partiellement payée'),
        ('Non payée', 'Non payée'),
    ], string='Statut paiement', default='Entièrement payée')
    status = fields.Selection([
        ('ok', 'OK'),
        ('Annulé', 'Annulé'),
        ('No-show', 'No-show'),
    ], string='Statut', default='ok')
    
    # Informations financières (optionnelles)
    rate = fields.Float(string='Tarif (XPF)')
    commission_amount = fields.Float(string='Commission (XPF)')
    
    @api.model
    def default_get(self, fields_list):
        """Valeurs par défaut du wizard"""
        res = super().default_get(fields_list)
        
        # Si on modifie une ligne existante, récupérer ses valeurs
        if 'line_to_edit' in self.env.context:
            line_id = self.env.context.get('line_to_edit')
            if line_id:
                line = self.env['booking.import.line'].browse(line_id)
                if line.exists():
                    res.update({
                        'line_to_edit': line.id,
                        'import_id': line.import_id.id,
                        'partner_id': line.partner_id.id,
                        'booker_id': line.booker_id.id,
                        'arrival_date': line.arrival_date,
                        'duration_nights': line.duration_nights,
                        'pax_nb': line.pax_nb,
                        'children': line.children,
                        'payment_status': line.payment_status,
                        'status': line.status,
                        'rate': line.rate,
                        'commission_amount': line.commission_amount,
                    })
        
        return res
    
    @api.onchange('create_new_partner')
    def _onchange_create_new_partner(self):
        """Reset des champs partenaire si on change le mode de création"""
        if self.create_new_partner:
            self.partner_id = False
        else:
            self.partner_name = False
            self.partner_phone = False
            self.partner_country_id = False
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Met à jour le booker par défaut"""
        if self.partner_id and not self.booker_id:
            self.booker_id = self.partner_id
    
    def action_add_line(self):
        """Ajoute ou modifie la ligne de réservation"""
        self.ensure_one()
        
        # Créer le client si nécessaire
        if self.create_new_partner:
            if not self.partner_name:
                raise UserError("Le nom du client est requis.")
            
            existing_partner = self.env['res.partner'].search([
                ('name', '=', self.partner_name)
            ], limit=1)
            
            if existing_partner:
                partner = existing_partner
            else:
                partner = self.env['res.partner'].create({
                    'name': self.partner_name,
                    'phone': self.partner_phone,
                    'country_id': self.partner_country_id.id if self.partner_country_id else False,
                    'company_id': self.env.user.company_id.id
                })
        else:
            partner = self.partner_id
        
        if not partner:
            raise UserError("Veuillez sélectionner ou créer un client.")
        
        # Préparer les valeurs de la ligne
        line_vals = {
            'import_id': self.import_id.id,
            'partner_id': partner.id,
            'booker_id': self.booker_id.id if self.booker_id else partner.id,
            'property_type_id': self.import_id.property_type_id.id,
            'arrival_date': self.arrival_date,
            'duration_nights': self.duration_nights,
            'pax_nb': self.pax_nb,
            'children': self.children,
            'payment_status': self.payment_status,
            'status': self.status,
            'rate': self.rate,
            'commission_amount': self.commission_amount,
        }
        
        # Créer ou modifier la ligne
        if self.line_to_edit:
            self.line_to_edit.write(line_vals)
            action_name = 'Réservation modifiée'
        else:
            self.env['booking.import.line'].create(line_vals)
            action_name = 'Réservation ajoutée'
        
        # Retourner au formulaire d'import
        return {
            'type': 'ir.actions.act_window',
            'name': action_name,
            'res_model': 'booking.import',
            'view_mode': 'form',
            'res_id': self.import_id.id,
            'target': 'current',
        }
    
    def action_cancel(self):
        """Annule l'ajout/modification de ligne"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'booking.import',
            'view_mode': 'form',
            'res_id': self.import_id.id,
            'target': 'current',
        }

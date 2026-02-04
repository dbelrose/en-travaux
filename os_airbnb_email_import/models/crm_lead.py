# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # ============================================
    # CHAMPS AIRBNB
    # ============================================

    airbnb_confirmation_code = fields.Char(
        string='Code Airbnb',
        help='Code de confirmation Airbnb (ex: HMRFYEX8YT)'
    )

    booking_line_id = fields.Many2one(
        'booking.import.line',
        string='Réservation',
        help='Réservation liée à ce lead'
    )

    email_log_id = fields.Many2one(
        'airbnb.email.log',
        string='Email source',
        help='Email Airbnb ayant généré ce lead'
    )

    is_airbnb_lead = fields.Boolean(
        string='Lead Airbnb',
        compute='_compute_is_airbnb_lead',
        store=True,
        help='Indique si ce lead provient d\'un email Airbnb'
    )

    @api.depends('airbnb_confirmation_code')
    def _compute_is_airbnb_lead(self):
        for lead in self:
            lead.is_airbnb_lead = bool(lead.airbnb_confirmation_code)

    # ============================================
    # ACTIONS
    # ============================================

    def action_view_booking(self):
        """Ouvre la réservation liée"""
        self.ensure_one()
        
        if not self.booking_line_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Réservation Airbnb',
            'res_model': 'booking.import.line',
            'res_id': self.booking_line_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_email_log(self):
        """Ouvre le log de l'email source"""
        self.ensure_one()
        
        if not self.email_log_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Email Airbnb',
            'res_model': 'airbnb.email.log',
            'res_id': self.email_log_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class BookingImportLine(models.Model):
    _inherit = 'booking.import.line'

    # ============================================
    # LIAISON CRM
    # ============================================

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead CRM',
        help='Lead CRM lié à cette réservation'
    )

    def action_view_lead(self):
        """Ouvre le lead CRM lié"""
        self.ensure_one()
        
        if not self.lead_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Lead Airbnb',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

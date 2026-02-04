# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AirbnbEmailLog(models.Model):
    _name = 'airbnb.email.log'
    _description = 'Journal des emails Airbnb'
    _order = 'date_received desc'
    _rec_name = 'subject'

    # ============================================
    # INFORMATIONS EMAIL
    # ============================================

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    subject = fields.Char(
        string='Sujet',
        required=True
    )

    from_email = fields.Char(
        string='Expéditeur',
        default='automated@airbnb.com'
    )

    date_received = fields.Datetime(
        string='Date réception',
        required=True,
        default=fields.Datetime.now
    )

    html_body = fields.Html(
        string='Corps HTML',
        help='Contenu HTML brut de l\'email'
    )

    # ============================================
    # TRAITEMENT
    # ============================================

    state = fields.Selection([
        ('processing', 'En cours'),
        ('success', 'Traité'),
        ('duplicate', 'Doublon'),
        ('error', 'Erreur'),
    ], string='État', default='processing', required=True)

    booking_reference = fields.Char(
        string='Code confirmation',
        help='Code de confirmation Airbnb extrait'
    )

    booking_line_id = fields.Many2one(
        'booking.import.line',
        string='Réservation créée',
        help='Réservation créée depuis cet email'
    )

    lead_id = fields.Many2one(
        'crm.lead',
        string='Lead CRM créé',
        help='Lead CRM créé depuis cet email'
    )

    error_message = fields.Text(
        string='Message d\'erreur',
        help='Détail de l\'erreur en cas d\'échec'
    )

    # ============================================
    # MÉTADONNÉES
    # ============================================

    create_date = fields.Datetime(
        string='Date création',
        readonly=True
    )

    write_date = fields.Datetime(
        string='Dernière modification',
        readonly=True
    )

    # ============================================
    # COMPUTED FIELDS
    # ============================================

    state_color = fields.Integer(
        string='Couleur état',
        compute='_compute_state_color'
    )

    @api.depends('state')
    def _compute_state_color(self):
        colors = {
            'processing': 4,  # Bleu
            'success': 10,    # Vert
            'duplicate': 3,   # Jaune
            'error': 1,       # Rouge
        }
        for log in self:
            log.state_color = colors.get(log.state, 0)

    # ============================================
    # ACTIONS
    # ============================================

    def action_view_booking(self):
        """Ouvre la réservation créée"""
        self.ensure_one()
        
        if not self.booking_line_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Réservation',
            'res_model': 'booking.import.line',
            'res_id': self.booking_line_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_lead(self):
        """Ouvre le lead CRM créé"""
        self.ensure_one()
        
        if not self.lead_id:
            return

        return {
            'type': 'ir.actions.act_window',
            'name': 'Lead CRM',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_retry_processing(self):
        """Retente le traitement de l'email"""
        self.ensure_one()

        if self.state not in ('error', 'duplicate'):
            return

        try:
            # Réinitialiser l'état
            self.write({'state': 'processing', 'error_message': False})

            # Re-parser l'email
            parser = self.env['airbnb.email.parser'].sudo()
            parsed_data = parser.parse_email_html(self.html_body, self.company_id)

            if not parsed_data:
                self.write({
                    'state': 'error',
                    'error_message': 'Impossible de parser l\'email'
                })
                return

            # Créer le lead si besoin
            if not self.lead_id:
                guest_name = f"{parsed_data.get('first_name', '')} {parsed_data.get('last_name', '')}".strip()
                lead = self.env['crm.lead'].sudo().create({
                    'name': f"Airbnb - {guest_name} - {parsed_data.get('property_type', '')}",
                    'type': 'opportunity',
                    'company_id': self.company_id.id,
                    'email_from': 'automated@airbnb.com',
                    'expected_revenue': parsed_data.get('rate_eur', 0),
                    'probability': 100,
                    'stage_id': self.env.ref('os_airbnb_email_import.crm_stage_airbnb_new').id,
                    'airbnb_confirmation_code': parsed_data.get('booking_reference'),
                    'email_log_id': self.id,
                })
                self.lead_id = lead.id

            # Traiter la réservation
            processor = self.env['airbnb.email.processor'].sudo()
            booking_line = processor.process_reservation(parsed_data, self.company_id, self.lead_id)

            # Mise à jour succès
            self.write({
                'state': 'success',
                'booking_reference': parsed_data.get('booking_reference'),
                'booking_line_id': booking_line.id,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Traitement réussi',
                    'message': f'Réservation {booking_line.booking_reference} créée',
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            self.write({
                'state': 'error',
                'error_message': str(e)
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Erreur',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                },
            }

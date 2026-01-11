# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AirbnbImportConfirmWizard(models.TransientModel):
    _name = 'airbnb.import.confirm.wizard'
    _description = 'Confirmation import Airbnb'

    # ============================================
    # DONNÉES EXTRAITES (lecture seule)
    # ============================================

    pdf_data = fields.Text(string='Données brutes', readonly=True)

    # Informations client
    partner_name = fields.Char(string='Nom du voyageur', readonly=True)
    partner_phone = fields.Char(string='Téléphone', readonly=True)
    partner_city = fields.Char(string='Ville', readonly=True)
    partner_country = fields.Char(string='Pays', readonly=True)
    partner_image = fields.Binary(string='Photo', readonly=True)

    # Informations réservation
    property_type = fields.Char(string='Type de logement', readonly=True)
    booking_reference = fields.Char(string='Code de confirmation', readonly=True)
    arrival_date = fields.Date(string='Arrivée', readonly=True)
    departure_date = fields.Date(string='Départ', readonly=True)
    reservation_date = fields.Date(string='Date de réservation', readonly=True)
    duration_nights = fields.Integer(string='Nuitées', readonly=True)

    # Informations financières
    rate_eur = fields.Float(string='Montant (EUR)', readonly=True, digits=(16, 2))
    rate_xpf = fields.Float(string='Montant (XPF)', readonly=True, digits=(16, 2))
    commission_eur = fields.Float(string='Commission (EUR)', readonly=True, digits=(16, 2))
    commission_xpf = fields.Float(string='Commission (XPF)', readonly=True, digits=(16, 2))

    # ============================================
    # DONNÉES MODIFIABLES
    # ============================================

    pax_nb = fields.Integer(
        string='👥 Nombre total de voyageurs',
        required=True,
        default=1,
        help='Nombre total de personnes (adultes + enfants)'
    )

    children = fields.Integer(
        string='👶 Nombre d\'enfants',
        default=0,
        help='Nombre d\'enfants de 12 ans ou moins'
    )

    adults = fields.Integer(
        string='🧑 Nombre d\'adultes',
        compute='_compute_adults',
        store=True,
        help='Calculé automatiquement : Total - Enfants'
    )

    @api.depends('pax_nb', 'children')
    def _compute_adults(self):
        for record in self:
            record.adults = max((record.pax_nb or 0) - (record.children or 0), 0)

    @api.constrains('children', 'pax_nb')
    def _check_children_count(self):
        for record in self:
            if record.children > record.pax_nb:
                raise UserError(_("Le nombre d'enfants ne peut pas dépasser le nombre total de voyageurs."))

    # ============================================
    # ALERTES ET MESSAGES
    # ============================================

    show_children_warning = fields.Boolean(
        string='Afficher alerte enfants',
        compute='_compute_warnings',
        help='Indique si on doit alerter l\'utilisateur sur les enfants'
    )

    warning_message = fields.Html(
        string='Message d\'alerte',
        compute='_compute_warnings'
    )

    @api.depends('pax_nb', 'children', 'adults')
    def _compute_warnings(self):
        for record in self:
            messages = []
            show_warning = False

            # Alerte si aucun enfant détecté
            if record.children == 0 and record.pax_nb > 0:
                show_warning = True
                messages.append(
                    '<div class="alert alert-warning" role="alert">'
                    '<strong>⚠️ Aucun enfant détecté dans le PDF</strong><br/>'
                    f'Tous les {record.pax_nb} voyageur(s) sont considérés comme adultes.<br/>'
                    'Si des enfants sont présents, veuillez ajuster ci-dessous.'
                    '</div>'
                )

            # Alerte taxe de séjour
            if record.adults > 0:
                estimated_tax = record.adults * record.duration_nights * 60.0
                messages.append(
                    '<div class="alert alert-info" role="status">'
                    '<strong>ℹ️ Taxe de séjour estimée</strong><br/>'
                    f'{record.adults} adulte(s) × {record.duration_nights} nuit(s) × 60 XPF = '
                    f'<strong>{estimated_tax:,.0f} XPF</strong>'
                    '</div>'
                )

            record.show_children_warning = show_warning
            record.warning_message = ''.join(messages) if messages else False

    # ============================================
    # DONNÉES TECHNIQUES
    # ============================================

    import_id = fields.Many2one('booking.import', string='Import', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner créé')
    parsed_data = fields.Text(string='Données parsées (JSON)')

    # ============================================
    # ACTIONS
    # ============================================

    def action_confirm(self):
        """Confirme l'import et crée la ligne de réservation"""
        self.ensure_one()

        try:
            # Récupérer les données parsées
            import json
            data = json.loads(self.parsed_data)

            # Mettre à jour avec les valeurs ajustées
            data['pax_nb'] = self.pax_nb
            data['children'] = self.children

            # Créer la ligne de réservation
            booking_line = self._create_booking_line_from_wizard(data)

            _logger.info(
                f"Réservation Airbnb confirmée : {booking_line.booking_reference} - "
                f"{self.pax_nb} voyageurs ({self.adults} adultes, {self.children} enfants)"
            )

            # Retourner vers la réservation créée
            return {
                'type': 'ir.actions.act_window',
                'name': _('Réservation importée'),
                'view_mode': 'form',
                'res_model': 'booking.import.line',
                'res_id': booking_line.id,
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Erreur lors de la confirmation import Airbnb: {e}")
            raise UserError(_("Erreur lors de la création de la réservation: %s") % str(e))

    def action_cancel(self):
        """Annule l'import"""
        return {'type': 'ir.actions.act_window_close'}

    def _create_booking_line_from_wizard(self, data):
        """Crée la ligne de réservation avec les données confirmées"""
        BookingLine = self.env['booking.import.line']

        # Récupérer le property_type
        importer = self.env['airbnb.pdf.importer']
        property_type = importer._get_or_create_property_type(data.get('property_type', 'Logement Airbnb'))

        # Conversion EUR → XPF
        rate_xpf = data.get('rate', 0) * 1000 / 8.38
        commission_xpf = data.get('commission_amount', 0) * 1000 / 8.38

        booking_vals = {
            'import_id': self.import_id.id,
            'partner_id': self.partner_id.id,
            'booker_id': self.partner_id.id,
            'property_type_id': property_type.id,
            'arrival_date': data.get('arrival_date'),
            'departure_date': data.get('departure_date'),
            'reservation_date': data.get('reservation_date', fields.Date.today()),
            'duration_nights': data.get('duration_nights', 1),
            'pax_nb': self.pax_nb,  # Valeur ajustée
            'children': self.children,  # Valeur ajustée
            'booking_reference': data.get('booking_reference', ''),
            'booking_id': data.get('booking_reference', ''),
            'payment_status': 'Entièrement payée',
            'status': 'ok',
            'rate': rate_xpf,
            'commission_amount': commission_xpf,
            'origin': 'airbnb',
            'import_type': 'pdf',
        }

        # Nettoyage des champs inexistants
        fields_to_check = ['children', 'booking_id', 'payment_status']
        for field_name in fields_to_check:
            if field_name in booking_vals and field_name not in BookingLine._fields:
                booking_vals.pop(field_name)

        booking_line = BookingLine.create(booking_vals)

        # Lier à la vue mensuelle
        if booking_line.arrival_date and booking_line.property_type_id:
            booking_month = self.env['booking.month'].create_or_update_month(
                property_type_id=booking_line.property_type_id.id,
                year=booking_line.arrival_date.year,
                month=booking_line.arrival_date.month,
                company_id=booking_line.company_id.id or self.env.company.id
            )
            booking_line.booking_month_id = booking_month.id

        return booking_line

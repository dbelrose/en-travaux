# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import datetime, timedelta, date

import logging

_logger = logging.getLogger(__name__)


def first_day_of_next_month(input_date):
    if input_date.month == 12:
        return date(input_date.year + 1, 1, 1)
    else:
        return date(input_date.year, input_date.month + 1, 1)


class BookingMonth(models.Model):
    _name = 'booking.month'
    _description = 'Vue mensuelle des réservations avec calcul des commissions'
    _order = 'year desc, month desc, property_type_id'
    _rec_name = 'display_name'

    # Identification de la vue mensuelle
    year = fields.Integer(string='Année', required=True)
    month = fields.Integer(string='Mois', required=True)
    property_type_id = fields.Many2one('product.template', string='Type d\'hébergement', required=True)
    company_id = fields.Many2one('res.company', string='Société', required=True,
                                 default=lambda self: self.env.company)

    # Nom d'affichage
    display_name = fields.Char(string='Nom', compute='_compute_display_name', store=True)
    month_name = fields.Char(string='Nom du mois', compute='_compute_month_name', store=True)

    # Statistiques des réservations
    total_reservations = fields.Integer(string='Nombre de réservations', compute='_compute_reservation_stats',
                                        store=True)
    total_nights = fields.Integer(string='Total nuitées', compute='_compute_reservation_stats', store=True)
    total_guests = fields.Integer(string='Total voyageurs', compute='_compute_reservation_stats', store=True)
    average_stay = fields.Float(string='Durée moyenne séjour', compute='_compute_reservation_stats', store=True)

    # Données financières
    total_revenue = fields.Float(string='Chiffre d\'affaires total', compute='_compute_financial_data', store=True)
    total_commission_booking = fields.Float(string='Commission Booking.com', compute='_compute_financial_data',
                                            store=True)
    total_tourist_tax = fields.Float(string='Taxe de séjour', compute='_compute_financial_data', store=True)

    # Commissions partenaires (calculées)
    concierge_commission = fields.Float(string='Commission concierge', compute='_compute_partner_commissions',
                                        store=True)
    concierge_partner_id = fields.Many2one('res.partner', string='Partenaire concierge',
                                           compute='_compute_concierge_partner_id', store=True)

    # Revenus nets
    net_revenue = fields.Float(string='Revenu net', compute='_compute_net_revenue', store=True)

    # État des factures
    booking_invoice_id = fields.Many2one('account.move', string='Facture Booking.com')
    concierge_invoice_id = fields.Many2one('account.move', string='Facture concierge')

    invoice_state = fields.Selection([
        ('none', 'Aucune facture'),
        ('booking_only', 'Booking seulement'),
        ('concierge_only', 'Concierge seulement'),
        ('both', 'Toutes les factures'),
    ], string='État facturation', compute='_compute_invoice_state', store=True)

    # Dates de période
    period_start = fields.Date(string='Début période', compute='_compute_period_dates', store=True)
    period_end = fields.Date(string='Fin période', compute='_compute_period_dates', store=True)

    # Contrainte d'unicité
    _sql_constraints = [
        ('unique_month_property',
         'unique(year, month, property_type_id, company_id)',
         'Une seule vue mensuelle par mois et par type d\'hébergement!')
    ]

    @api.depends('year', 'month', 'property_type_id')
    def _compute_display_name(self):
        for record in self:
            if record.month and record.year and record.property_type_id:
                try:
                    month_name = datetime(1900, record.month, 1).strftime('%B').capitalize()
                    record.display_name = f"{month_name} {record.year} - {record.property_type_id.name}"
                except (ValueError, AttributeError):
                    record.display_name = f"{record.month:02d}/{record.year} - {record.property_type_id.name or 'Sans propriété'}"
            else:
                record.display_name = "Vue mensuelle incomplète"

    @api.depends('month')
    def _compute_month_name(self):
        for record in self:
            if record.month:
                try:
                    record.month_name = datetime(1900, record.month, 1).strftime('%B').capitalize()
                except ValueError:
                    record.month_name = f"Mois {record.month}"
            else:
                record.month_name = ""

    @api.depends('year', 'month')
    def _compute_period_dates(self):
        for record in self:
            if record.year and record.month:
                try:
                    record.period_start = datetime(record.year, record.month, 1).date()
                    # Dernier jour du mois
                    if record.month == 12:
                        next_month = datetime(record.year + 1, 1, 1)
                    else:
                        next_month = datetime(record.year, record.month + 1, 1)
                    record.period_end = (next_month - timedelta(days=1)).date()
                except ValueError:
                    record.period_start = False
                    record.period_end = False
            else:
                record.period_start = False
                record.period_end = False

    @api.depends('year', 'month', 'property_type_id')
    def _compute_reservation_stats(self):
        for record in self:
            if not record.year or not record.month or not record.property_type_id:
                record._reset_reservation_stats()
                continue

            # Rechercher toutes les réservations du mois
            reservations = self._get_month_reservations(record)

            record.total_reservations = len(reservations)
            record.total_nights = sum(r.total_nights for r in reservations)
            record.total_guests = sum(r.pax_nb for r in reservations)

            if record.total_reservations > 0:
                record.average_stay = sum(r.duration_nights for r in reservations) / record.total_reservations
            else:
                record.average_stay = 0.0

    @api.depends('year', 'month', 'property_type_id')
    def _compute_financial_data(self):
        for record in self:
            if not record.year or not record.month or not record.property_type_id:
                record._reset_financial_data()
                continue

            reservations = self._get_month_reservations(record)

            record.total_revenue = sum(r.rate for r in reservations if r.rate)
            record.total_commission_booking = sum(r.commission_amount for r in reservations if r.commission_amount)
            record.total_tourist_tax = sum(r.tax_amount for r in reservations if r.tax_amount)

    @api.depends('total_revenue', 'total_commission_booking', 'total_tourist_tax', 'property_type_id')
    def _compute_partner_commissions(self):
        for record in self:
            if not record.total_revenue:
                record.concierge_commission = 0.0
                continue

            # Calculer la base de commission (CA - commission Booking - taxe séjour)
            commission_base = record.total_revenue - record.total_commission_booking - record.total_tourist_tax

            # Commission concierge = 20% de la base
            if commission_base > 0:
                record.concierge_commission = commission_base * 0.20
            else:
                record.concierge_commission = 0.0

    @api.depends('property_type_id')
    def _compute_concierge_partner_id(self):
        for record in self:
            record.concierge_partner_id = False

            if not record.property_type_id or not record.property_type_id.company_id:
                continue

            # Récupérer le type de relation "Concierge" via external ID
            try:
                concierge_relation_base = self.env.ref('os_hospitality_managment_bis.relation_type_concierge')
                # Rechercher le type de sélection correspondant (côté concierge -> propriété)
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('type_id', '=', concierge_relation_base.id),
                    ('is_inverse', '=', False)  # Concierge vers Société
                ], limit=1)
            except ValueError:
                # Fallback si l'external ID n'existe pas
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('name', 'ilike', 'Concierge')
                ], limit=1)

            if not concierge_relation_type:
                continue

            # Rechercher la relation où :
            # - other_partner_id correspond à la société de la propriété
            # - type_selection_id correspond au type "Concierge"
            relation = self.env['res.partner.relation.all'].search([
                ('other_partner_id', '=', record.property_type_id.company_id.partner_id.id),
                ('type_selection_id', '=', concierge_relation_type.id),
                ('active', '=', True)  # Seulement les relations actives
            ], limit=1)

            if relation:
                record.concierge_partner_id = relation.this_partner_id
            else:
                # Fallback : utiliser le partenaire de la société comme avant
                record.concierge_partner_id = record.property_type_id.company_id.partner_id

    @api.depends('total_revenue', 'total_commission_booking', 'total_tourist_tax', 'concierge_commission')
    def _compute_net_revenue(self):
        for record in self:
            record.net_revenue = (record.total_revenue -
                                  record.total_commission_booking -
                                  record.total_tourist_tax -
                                  record.concierge_commission)

    @api.depends('booking_invoice_id', 'concierge_invoice_id')
    def _compute_invoice_state(self):
        for record in self:
            has_booking = bool(record.booking_invoice_id)
            has_concierge = bool(record.concierge_invoice_id)

            if has_booking and has_concierge:
                record.invoice_state = 'both'
            elif has_booking:
                record.invoice_state = 'booking_only'
            elif has_concierge:
                record.invoice_state = 'concierge_only'
            else:
                record.invoice_state = 'none'

    def _get_month_reservations(self, record):
        """Récupère toutes les réservations du mois pour cette propriété"""
        if not record.period_start or not record.period_end:
            return self.env['booking.import.line']

        return self.env['booking.import.line'].search([
            ('property_type_id', '=', record.property_type_id.id),
            ('arrival_date', '>=', record.period_start),
            ('arrival_date', '<=', record.period_end),
            ('status', '=', 'ok')  # Seules les réservations confirmées
        ])

    def _reset_reservation_stats(self):
        self.total_reservations = 0
        self.total_nights = 0
        self.total_guests = 0
        self.average_stay = 0

    def _reset_financial_data(self):
        self.total_revenue = 0
        self.total_commission_booking = 0
        self.total_tourist_tax = 0

    def action_recalculate(self):
        """Force le recalcul des données"""
        self._compute_reservation_stats()
        self._compute_financial_data()
        self._compute_partner_commissions()
        return True

    def action_generate_concierge_invoice(self):
        """Génère une facture de commission concierge mensuelle globale (toutes propriétés)"""
        self.ensure_one()

        # Rechercher tous les enregistrements booking.month pour ce mois/année
        monthly_records = self.env['booking.month'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id)
        ])

        if not monthly_records:
            raise ValueError("Aucune donnée mensuelle trouvée pour cette période.")

        # Calculer le total des commissions concierge
        total_commission = sum(record.concierge_commission for record in monthly_records)

        if total_commission <= 0:
            raise ValueError("Aucune commission concierge à facturer pour cette période.")

        # Utiliser le concierge du premier enregistrement (ils devraient tous avoir le même)
        concierge_partner = False
        for record in monthly_records:
            if record.concierge_partner_id:
                concierge_partner = record.concierge_partner_id
                break

        if not concierge_partner:
            raise ValueError("Aucun partenaire concierge configuré.")

        # Mois en français
        month_names_fr = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                          'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        month_name_fr = month_names_fr[self.month]

        # Vérifier qu'une facture globale n'existe pas déjà pour ce mois
        ref_pattern = f"Commission concierge {month_name_fr} {self.year}"

        existing_invoice = self.env['account.move'].search([
            ('partner_id', '=', concierge_partner.id),
            ('ref', 'ilike', ref_pattern),
            ('move_type', '=', 'in_invoice'),
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel')
        ], limit=1)

        if existing_invoice:
            # Mettre à jour tous les enregistrements monthly avec cette facture
            monthly_records.write({'concierge_invoice_id': existing_invoice.id})
            raise ValueError(f"Une facture concierge globale existe déjà pour {month_name_fr} {self.year}.")

        # Compte de charge pour commissions
        account_id = self.env['account.account'].search([
            ('code', '=', '62220000'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not account_id:
            raise ValueError("Le compte de charge '62220000' n'existe pas.")

        # Journal de factures fournisseur
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé.")

        # Dates de facturation
        invoice_date = self.period_end  # Dernier jour du mois
        invoice_date_due = fields.Date.add(invoice_date, days=30)

        # Préparer les lignes de facture regroupées par propriété
        invoice_lines = []

        for monthly_record in monthly_records:
            if monthly_record.concierge_commission > 0:
                # Récupérer les réservations pour cette propriété ce mois-ci
                reservations = monthly_record._get_month_reservations(monthly_record)

                if reservations:
                    # Une ligne récapitulative par propriété
                    line_name = (f"Commission concierge {monthly_record.property_type_id.name} - "
                                 f"{month_name_fr} {self.year} "
                                 f"({len(reservations)} réservations)")

                    line_vals = (0, 0, {
                        'name': line_name,
                        'quantity': 1,
                        'price_unit': monthly_record.concierge_commission,
                        'account_id': account_id.id,
                        'tax_ids': [(6, 0, [])],  # Pas de taxes
                    })
                    invoice_lines.append(line_vals)

        if not invoice_lines:
            raise ValueError("Aucune ligne de commission à facturer.")

        # Référence de la facture globale
        ref = f"Commission concierge {month_name_fr} {self.year}"

        # Terme de paiement
        try:
            payment_term = self.env.ref('account.account_payment_term_30days')
        except:
            payment_term = False

        # Créer la facture fournisseur
        invoice_vals = {
            'partner_id': concierge_partner.id,
            'move_type': 'in_invoice',
            'invoice_date': invoice_date,
            'invoice_date_due': invoice_date_due,
            'ref': ref,
            'narration': f"Commission concierge pour {month_name_fr} {self.year} - Toutes propriétés",
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'currency_id': self.company_id.currency_id.id,
            'invoice_line_ids': invoice_lines,
            'invoice_payment_term_id': payment_term.id if payment_term else False,
        }

        try:
            invoice = self.env['account.move'].with_context(
                default_move_type='in_invoice',
                move_type='in_invoice',
                journal_type='purchase'
            ).create(invoice_vals)

            # Lier la facture à TOUS les enregistrements mensuels de cette période
            monthly_records.write({'concierge_invoice_id': invoice.id})

            # Forcer le recalcul des champs automatiques
            invoice._onchange_partner_id()

            # Valider la facture
            invoice.action_post()

            # Générer les factures client correspondantes dans les sociétés partenaires
            self._generate_customer_concierge_invoices(monthly_records, month_name_fr, invoice_date, invoice_date_due)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Facture commission concierge',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
                'target': 'current',
            }

        except Exception as e:
            raise ValueError(f"Erreur lors de la création de la facture concierge: {str(e)}")

    def action_generate_booking_invoice(self):
        """Génère une facture de commission Booking.com mensuelle globale (toutes propriétés)"""
        self.ensure_one()

        # Rechercher tous les enregistrements booking.month pour ce mois/année
        monthly_records = self.env['booking.month'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id)
        ])

        if not monthly_records:
            raise ValueError("Aucune donnée mensuelle trouvée pour cette période.")

        # Calculer le total des commissions Booking.com
        total_commission = sum(record.total_commission_booking for record in monthly_records)

        if total_commission <= 0:
            raise ValueError("Aucune commission Booking.com à facturer pour cette période.")

        # Récupérer le partenaire Booking.com
        booking_partner = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)
        if not booking_partner:
            raise ValueError("Le partenaire 'Booking.com' n'existe pas.")

        # Mois en français
        month_names_fr = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                          'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
        month_name_fr = month_names_fr[self.month]

        # Vérifier qu'une facture globale n'existe pas déjà pour ce mois
        ref_pattern = f"Commission Booking.com {month_name_fr} {self.year}"

        existing_invoice = self.env['account.move'].search([
            ('partner_id', '=', booking_partner.id),
            ('ref', 'ilike', ref_pattern),
            ('move_type', '=', 'in_invoice'),
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel')
        ], limit=1)

        if existing_invoice:
            # Mettre à jour tous les enregistrements monthly avec cette facture
            monthly_records.write({'booking_invoice_id': existing_invoice.id})
            raise ValueError(f"Une facture Booking.com globale existe déjà pour {month_name_fr} {self.year}.")

        # Compte de charge pour commissions
        account_id = self.env['account.account'].search([
            ('code', '=', '62220000'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not account_id:
            raise ValueError("Le compte de charge '62220000' n'existe pas.")

        # Journal de factures fournisseur
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé.")

        # Dates de facturation (premier jour du mois suivant)
        if self.month == 12:
            next_month_date = fields.Date.from_string(f"{self.year + 1}-01-01")
        else:
            next_month_date = fields.Date.from_string(f"{self.year}-{self.month + 1:02d}-01")

        invoice_date = next_month_date
        invoice_date_due = fields.Date.add(invoice_date, days=30)

        # Préparer les lignes de facture regroupées par propriété
        invoice_lines = []

        for monthly_record in monthly_records:
            if monthly_record.total_commission_booking > 0:
                # Récupérer les réservations pour cette propriété ce mois-ci
                reservations = monthly_record._get_month_reservations(monthly_record)

                if reservations:
                    # Une ligne récapitulative par propriété
                    line_name = (f"Commission Booking.com {monthly_record.property_type_id.name} - "
                                 f"{month_name_fr} {self.year} "
                                 f"({len(reservations)} réservations)")

                    line_vals = (0, 0, {
                        'name': line_name,
                        'quantity': 1,
                        'price_unit': monthly_record.total_commission_booking,
                        'account_id': account_id.id,
                        'tax_ids': [(6, 0, [])],  # Pas de taxes
                    })
                    invoice_lines.append(line_vals)

        if not invoice_lines:
            raise ValueError("Aucune ligne de commission à facturer.")

        # Référence de la facture globale
        ref = f"Commission Booking.com {month_name_fr} {self.year}"

        # Terme de paiement
        try:
            payment_term = self.env.ref('account.account_payment_term_30days')
        except:
            payment_term = False

        # Créer la facture fournisseur
        invoice_vals = {
            'partner_id': booking_partner.id,
            'move_type': 'in_invoice',
            'invoice_date': invoice_date,
            'invoice_date_due': invoice_date_due,
            'ref': ref,
            'narration': f"Commissions Booking.com pour {month_name_fr} {self.year} - Toutes propriétés",
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'currency_id': self.company_id.currency_id.id,
            'invoice_line_ids': invoice_lines,
            'invoice_payment_term_id': payment_term.id if payment_term else False,
        }

        try:
            invoice = self.env['account.move'].with_context(
                default_move_type='in_invoice',
                move_type='in_invoice',
                journal_type='purchase'
            ).create(invoice_vals)

            # Lier la facture à TOUS les enregistrements mensuels de cette période
            monthly_records.write({'booking_invoice_id': invoice.id})

            # Forcer le recalcul des champs automatiques
            invoice._onchange_partner_id()

            # Valider la facture
            invoice.action_post()

            # Générer les factures client correspondantes dans les sociétés partenaires
            self._generate_customer_booking_invoices(monthly_records, month_name_fr, invoice_date, invoice_date_due)

            return {
                'type': 'ir.actions.act_window',
                'name': 'Facture commission Booking.com',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
                'target': 'current',
            }

        except Exception as e:
            raise ValueError(f"Erreur lors de la création de la facture Booking.com: {str(e)}")

    def _generate_customer_concierge_invoices(self, monthly_records, month_name_fr, invoice_date, invoice_date_due):
        """Génère les factures client concierge dans chaque société propriétaire"""

        # Regrouper les enregistrements par société propriétaire
        companies_data = {}

        for monthly_record in monthly_records:
            if monthly_record.concierge_commission > 0 and monthly_record.property_type_id.company_id:
                property_company = monthly_record.property_type_id.company_id

                if property_company.id not in companies_data:
                    companies_data[property_company.id] = {
                        'company': property_company,
                        'records': [],
                        'total_commission': 0
                    }

                companies_data[property_company.id]['records'].append(monthly_record)
                companies_data[property_company.id]['total_commission'] += monthly_record.concierge_commission

        # Créer une facture client dans chaque société propriétaire
        for company_data in companies_data.values():
            try:
                self._create_customer_concierge_invoice(
                    company_data['company'],
                    company_data['records'],
                    month_name_fr,
                    invoice_date,
                    invoice_date_due,
                    company_data['total_commission']
                )
            except Exception as e:
                _logger.warning(f"Erreur création facture client concierge pour {company_data['company'].name}: {e}")

    def _create_customer_concierge_invoice(self, property_company, monthly_records, month_name_fr, invoice_date,
                                           invoice_date_due, total_commission):
        """Crée une facture client concierge dans la société propriétaire"""

        # Vérifier que la facture n'existe pas déjà
        ref = f"Commission concierge {month_name_fr} {self.year}"

        existing_customer_invoice = self.env['account.move'].search([
            ('partner_id', '=', self.company_id.partner_id.id),  # La société actuelle comme client
            ('ref', '=', ref),
            ('move_type', '=', 'out_invoice'),
            ('company_id', '=', property_company.id)  # Dans la société propriétaire
        ], limit=1)

        if existing_customer_invoice:
            return existing_customer_invoice

        # Compte de produit pour commissions dans la société propriétaire
        revenue_account = self.env['account.account'].search([
            ('code', '=like', '701%'),  # Compte de vente
            ('company_id', '=', property_company.id)
        ], limit=1)

        if not revenue_account:
            # Utiliser le compte de vente par défaut
            revenue_account = self.env['account.account'].search([
                ('user_type_id.name', 'ilike', 'income'),
                ('company_id', '=', property_company.id)
            ], limit=1)

        if not revenue_account:
            _logger.warning(f"Aucun compte de produit trouvé pour la société {property_company.name}")
            return False

        # Journal de vente dans la société propriétaire
        sale_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', property_company.id)
        ], limit=1)

        if not sale_journal:
            _logger.warning(f"Aucun journal de vente trouvé pour la société {property_company.name}")
            return False

        # Préparer les lignes de facture
        invoice_lines = []

        for monthly_record in monthly_records:
            if monthly_record.concierge_commission > 0:
                reservations = monthly_record._get_month_reservations(monthly_record)

                line_name = (f"Commission concierge {monthly_record.property_type_id.name} - "
                             f"{month_name_fr} {self.year} "
                             f"({len(reservations)} réservations)")

                line_vals = (0, 0, {
                    'name': line_name,
                    'quantity': 1,
                    'price_unit': monthly_record.concierge_commission,
                    'account_id': revenue_account.id,
                    'tax_ids': [(6, 0, [])],  # Pas de taxes
                })
                invoice_lines.append(line_vals)

        # Créer la facture client
        customer_invoice_vals = {
            'partner_id': self.company_id.partner_id.id,  # La société actuelle comme client
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'invoice_date_due': invoice_date_due,
            'ref': ref,
            'narration': f"Facture commission concierge pour {month_name_fr} {self.year}",
            'company_id': property_company.id,
            'journal_id': sale_journal.id,
            'currency_id': property_company.currency_id.id,
            'invoice_line_ids': invoice_lines,
        }

        customer_invoice = self.env['account.move'].with_context(
            default_move_type='out_invoice',
            move_type='out_invoice',
            journal_type='sale'
        ).with_company(property_company.id).create(customer_invoice_vals)

        # Forcer le recalcul et valider
        customer_invoice._onchange_partner_id()
        customer_invoice.action_post()

        return customer_invoice

    def _generate_customer_booking_invoices(self, monthly_records, month_name_fr, invoice_date, invoice_date_due):
        """Génère les factures client Booking.com dans chaque société propriétaire"""

        # Regrouper les enregistrements par société propriétaire
        companies_data = {}

        for monthly_record in monthly_records:
            if monthly_record.total_commission_booking > 0 and monthly_record.property_type_id.company_id:
                property_company = monthly_record.property_type_id.company_id

                if property_company.id not in companies_data:
                    companies_data[property_company.id] = {
                        'company': property_company,
                        'records': [],
                        'total_commission': 0
                    }

                companies_data[property_company.id]['records'].append(monthly_record)
                companies_data[property_company.id]['total_commission'] += monthly_record.total_commission_booking

        # Créer une facture client dans chaque société propriétaire
        for company_data in companies_data.values():
            try:
                self._create_customer_booking_invoice(
                    company_data['company'],
                    company_data['records'],
                    month_name_fr,
                    invoice_date,
                    invoice_date_due,
                    company_data['total_commission']
                )
            except Exception as e:
                _logger.warning(f"Erreur création facture client Booking pour {company_data['company'].name}: {e}")

    def _create_customer_booking_invoice(self, property_company, monthly_records, month_name_fr, invoice_date,
                                         invoice_date_due, total_commission):
        """Crée une facture client Booking.com dans la société propriétaire"""

        # Vérifier que la facture n'existe pas déjà
        ref = f"Commission Booking.com {month_name_fr} {self.year}"

        existing_customer_invoice = self.env['account.move'].search([
            ('partner_id', '=', self.company_id.partner_id.id),  # La société actuelle comme client
            ('ref', '=', ref),
            ('move_type', '=', 'out_invoice'),
            ('company_id', '=', property_company.id)  # Dans la société propriétaire
        ], limit=1)

        if existing_customer_invoice:
            return existing_customer_invoice

        # Compte de produit pour commissions dans la société propriétaire
        revenue_account = self.env['account.account'].search([
            ('code', '=like', '701%'),  # Compte de vente
            ('company_id', '=', property_company.id)
        ], limit=1)

        if not revenue_account:
            # Utiliser le compte de vente par défaut
            revenue_account = self.env['account.account'].search([
                ('user_type_id.name', 'ilike', 'income'),
                ('company_id', '=', property_company.id)
            ], limit=1)

        if not revenue_account:
            _logger.warning(f"Aucun compte de produit trouvé pour la société {property_company.name}")
            return False

        # Journal de vente dans la société propriétaire
        sale_journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', property_company.id)
        ], limit=1)

        if not sale_journal:
            _logger.warning(f"Aucun journal de vente trouvé pour la société {property_company.name}")
            return False

        # Préparer les lignes de facture
        invoice_lines = []

        for monthly_record in monthly_records:
            if monthly_record.total_commission_booking > 0:
                reservations = monthly_record._get_month_reservations(monthly_record)

                line_name = (f"Commission Booking.com {monthly_record.property_type_id.name} - "
                             f"{month_name_fr} {self.year} "
                             f"({len(reservations)} réservations)")

                line_vals = (0, 0, {
                    'name': line_name,
                    'quantity': 1,
                    'price_unit': monthly_record.total_commission_booking,
                    'account_id': revenue_account.id,
                    'tax_ids': [(6, 0, [])],  # Pas de taxes
                })
                invoice_lines.append(line_vals)

        # Créer la facture client
        customer_invoice_vals = {
            'partner_id': self.company_id.partner_id.id,  # La société actuelle comme client
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'invoice_date_due': invoice_date_due,
            'ref': ref,
            'narration': f"Facture commission Booking.com pour {month_name_fr} {self.year}",
            'company_id': property_company.id,
            'journal_id': sale_journal.id,
            'currency_id': property_company.currency_id.id,
            'invoice_line_ids': invoice_lines,
        }

        customer_invoice = self.env['account.move'].with_context(
            default_move_type='out_invoice',
            move_type='out_invoice',
            journal_type='sale'
        ).with_company(property_company.id).create(customer_invoice_vals)

        # Forcer le recalcul et valider
        customer_invoice._onchange_partner_id()
        customer_invoice.action_post()

        return customer_invoice

    def action_generate_all_invoices(self):
        """Génère toutes les factures mensuelles globales (Booking.com et concierge)"""
        self.ensure_one()

        results = []

        # Générer la facture Booking.com si nécessaire
        try:
            # Vérifier s'il y a des commissions Booking à facturer ce mois-ci
            monthly_records = self.env['booking.month'].search([
                ('year', '=', self.year),
                ('month', '=', self.month),
                ('company_id', '=', self.company_id.id)
            ])

            total_booking_commission = sum(record.total_commission_booking for record in monthly_records)
            has_booking_invoice = any(record.booking_invoice_id for record in monthly_records)

            if total_booking_commission > 0 and not has_booking_invoice:
                self.action_generate_booking_invoice()
                results.append("Factures Booking.com (fournisseur + clients) créées")
            elif has_booking_invoice:
                results.append("Facture Booking.com globale existe déjà")
            else:
                results.append("Aucune commission Booking.com à facturer")

        except Exception as e:
            results.append(f"Erreur facture Booking.com: {str(e)}")

        # Générer la facture concierge si nécessaire
        try:
            total_concierge_commission = sum(record.concierge_commission for record in monthly_records)
            has_concierge_invoice = any(record.concierge_invoice_id for record in monthly_records)

            if total_concierge_commission > 0 and not has_concierge_invoice:
                self.action_generate_concierge_invoice()
                results.append("Factures concierge (fournisseur + clients) créées")
            elif has_concierge_invoice:
                results.append("Facture concierge globale existe déjà")
            else:
                results.append("Aucune commission concierge à facturer")

        except Exception as e:
            results.append(f"Erreur facture concierge: {str(e)}")

        # Afficher un message de résultat
        message = "\n".join(results)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Génération de factures globales',
                'message': message,
                'type': 'success' if 'Erreur' not in message else 'warning',
                'sticky': False,
            }
        }

    @api.model
    def create_or_update_month(self, property_type_id, year, month, company_id=None):
        """
        Crée ou met à jour un enregistrement BookingMonth pour la période donnée.

        Args:
            year (int): Année de la période
            month (int): Mois de la période (1-12)
            property_type_id (int): ID du type d'hébergement
            company_id (int, optional): ID de la société. Si None, utilise la société courante

        Returns:
            booking.month: L'enregistrement créé ou mis à jour
        """
        # Validation des paramètres
        if not isinstance(year, int) or year < 1900 or year > 2100:
            raise ValueError(f"Année invalide: {year}")

        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValueError(f"Mois invalide: {month}")

        if not property_type_id:
            raise ValueError("Le type d'hébergement est obligatoire")

        # Utiliser la société courante si non spécifiée
        if company_id is None:
            company_id = self.env.company.id

        # Vérifier que le type d'hébergement existe
        property_type = property_type_id if hasattr(property_type_id, 'exists') else self.env['product.template'].browse(property_type_id)
        if not property_type.exists():
            raise ValueError(f"Type d'hébergement inexistant: {property_type_id}")

        # Vérifier que la société existe
        company = company_id if hasattr(company_id, 'exists') else self.env['product.template'].browse(company_id)
        if not company.exists():
            raise ValueError(f"Société inexistante: {company_id}")

        # Rechercher un enregistrement existant
        domain = [
            ('year', '=', year),
            ('month', '=', month),
            ('property_type_id', '=', property_type.id),
            ('company_id', '=', company_id)
        ]

        existing_record = self.search(domain, limit=1)

        if existing_record:
            # Mettre à jour l'enregistrement existant
            # Les champs calculés se mettront à jour automatiquement
            existing_record._compute_display_name()
            existing_record._compute_month_name()
            existing_record._compute_period_dates()
            existing_record._compute_reservation_stats()
            existing_record._compute_financial_data()
            existing_record._compute_partner_commissions()
            existing_record._compute_concierge_partner_id()
            existing_record._compute_net_revenue()
            existing_record._compute_invoice_state()

            return existing_record
        else:
            # Créer un nouvel enregistrement
            values = {
                'year': year,
                'month': month,
                'property_type_id': property_type_id,
                'company_id': company_id,
            }

            new_record = self.create(values)
            return new_record

    # Méthode utilitaire pour forcer le recalcul
    def _ensure_concierge_partner(self):
        """Force le recalcul et vérifie la présence du partenaire concierge."""
        self.ensure_one()

        # Force le recalcul en invalidant le cache
        self.invalidate_recordset(['concierge_partner_id'])

        # Accéder au champ pour déclencher le recalcul
        concierge = self.concierge_partner_id

        if not concierge:
            raise ValueError(
                f"Aucun partenaire concierge configuré pour {self.display_name}. "
                f"Veuillez configurer une relation 'Concierge' avec la société "
                f"{self.property_type_id.company_id.name}."
            )

        return concierge

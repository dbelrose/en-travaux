# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
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
    average_rate = fields.Monetary(string='Tarif moyen', compute='_compute_reservation_stats',
                                   currency_field='company_currency_id', store=True)

    # Données financières
    gross_revenue = fields.Monetary(string='Chiffre d\'affaires période', compute='_compute_net_revenue',
                                    currency_field='company_currency_id', store=True)
    total_costs = fields.Monetary(string='Coût de revient total', compute='_compute_net_revenue',
                                  currency_field='company_currency_id', store=True)
    profit_margin = fields.Monetary(string='Bénéfice', compute='_compute_net_revenue',
                                    currency_field='company_currency_id', store=True)

    revenue_booking_com = fields.Monetary(string='Chiffre d\'affaires Booking', compute='_compute_channel_revenue',
                                          currency_field='company_currency_id', store=True)
    revenue_direct = fields.Monetary(string='Chiffre d\'affaires direct', compute='_compute_channel_revenue',
                                     currency_field='company_currency_id', store=True)
    revenue_other_channels = fields.Monetary(string='Autre chiffre d\'affaires', compute='_compute_channel_revenue',
                                             currency_field='company_currency_id', store=True)

    total_revenue = fields.Monetary(string='Chiffre d\'affaires total', compute='_compute_financial_data',
                                    currency_field='company_currency_id', store=True)
    total_commission_booking = fields.Monetary(string='Commission Booking.com', compute='_compute_financial_data',
                                               currency_field='company_currency_id', store=True)
    total_tourist_tax = fields.Monetary(string='Taxe de séjour', compute='_compute_financial_data',
                                        currency_field='company_currency_id', store=True)

    # Produit et paramètres de commission concierge
    concierge_service_id = fields.Many2one('product.product', string='Service conciergerie',
                                           compute='_compute_concierge_service', store=True)
    concierge_commission_rate = fields.Float(string='Taux commission (%)',
                                             compute='_compute_concierge_service', store=True)

    # Commissions partenaires (calculées)
    concierge_commission_base = fields.Monetary(string='Base commission concierge',
                                                compute='_compute_base_concierge_commission',
                                                currency_field='company_currency_id', store=True)
    concierge_commission = fields.Monetary(string='Commission concierge', compute='_compute_partner_commissions',
                                           currency_field='company_currency_id', store=True)
    concierge_partner_id = fields.Many2one('res.partner', string='Partenaire concierge',
                                           compute='_compute_concierge_partner_id', store=True)

    # Revenus nets
    net_revenue = fields.Monetary(string='Revenu net', compute='_compute_net_revenue',
                                  currency_field='company_currency_id', store=True)

    # État des factures
    booking_invoice_id = fields.Many2one('account.move', string='Facture Booking.com')
    concierge_invoice_id = fields.Many2one('account.move', string='Facture fournisseur concierge')
    concierge_client_invoice_id = fields.Many2one('account.move', string='Facture client concierge')
    tourist_tax_invoice_id = fields.Many2one('account.move', string='Facture concierge')

    invoice_state = fields.Selection([
        ('none', 'Aucune facture'),
        ('partial', 'Partiel'),
        ('complete', 'Toutes les factures'),
    ], string='État facturation', compute='_compute_invoice_state', store=True)

    # Dates de période
    period_start = fields.Date(string='Début période', compute='_compute_period_dates', store=True)
    period_end = fields.Date(string='Fin période', compute='_compute_period_dates', store=True)
    last_calculation_date = fields.Date(string='Date de calcul', compute='action_recalculate', store=True)

    calculation_user_id = fields.Many2one('res.users', string='Calculé par')

    # État
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('calculated', 'Calculé'),
        ('posted', 'Publié')
    ], string='État', default='draft')

    company_currency_id = fields.Many2one('res.currency', string="Company Currency", related='company_id.currency_id')

    origin = fields.Selection([
        ('airbnb', 'Airbnb'),
        ('booking.com', 'Booking.com'),
        ('other', 'Autre'),
    ], string='Source', default='booking.com')

    import_type = fields.Selection([
        ('file', 'XLS'),
        ('pdf', 'PDF'),
        ('manual', 'Saisie manuelle')
    ], string='Type d\'import', default='file')


    # Contrainte d'unicité
    _sql_constraints = [
        ('unique_month_property',
         'unique(year, month, property_type_id, company_id)',
         'Une seule vue mensuelle par mois et par type d\'hébergement!')
    ]

    @api.depends('company_id')
    def _compute_company_currency(self):
        for rec in self:
            if not rec.company_id:
                rec.company_currency = self.env.company.currency_id
            else:
                rec.company_currency = rec.company_id.currency_id

    @api.depends('property_type_id')
    def _compute_concierge_partner_id(self):
        for record in self:
            record.concierge_partner_id = False

            if not record.property_type_id or not record.property_type_id.company_id:
                continue

            # Récupérer le type de relation "Concierge" via external ID
            try:
                concierge_relation_base = self.env.ref('os_hospitality_managment.relation_type_concierge')
                _logger.info(f"concierge_relation_base {concierge_relation_base.id}")
                # Rechercher le type de sélection correspondant (côté concierge -> propriété)
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('type_id', '=', concierge_relation_base.id),
                    ('is_inverse', '=', False)  # Concierge vers Société
                ], limit=1)
                _logger.info(f"concierge_relation_type {concierge_relation_type.id}")

            except ValueError:
                # Fallback si l'external ID n'existe pas
                concierge_relation_type = self.env['res.partner.relation.type.selection'].search([
                    ('name', 'ilike', 'Concierge')
                ], limit=1)
                _logger.info(f"Fallback : concierge_relation_type {concierge_relation_type.id}")

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
            _logger.info(f"relation {relation.id}")

            if relation:
                record.concierge_partner_id = relation.this_partner_id
                _logger.info(f"concierge {record.concierge_partner_id.id}")
            else:
                # Fallback : utiliser le partenaire de la société comme avant
                record.concierge_partner_id = record.property_type_id.company_id.partner_id
                _logger.info(f"Fallback : concierge {record.concierge_partner_id.id}")

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

        # Générer les factures concierge si nécessaire
        try:
            total_concierge_commission = sum(record.concierge_commission for record in monthly_records)
            has_concierge_invoice = any(record.concierge_invoice_id for record in monthly_records)

            if total_concierge_commission > 0 and not has_concierge_invoice:
                self.action_generate_both_concierge_invoices()
                results.append("Factures concierge (fournisseur + clients) créées")
            elif has_concierge_invoice:
                results.append("Factures concierge existent déjà")
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

    @api.depends('year', 'month', 'property_type_id')
    def _compute_display_name(self):
        for record in self:
            if record.month and record.year and record.property_type_id:
                try:
                    # month_name = datetime(1900, record.month, 1).strftime('%B').capitalize()
                    record.display_name = f"{record.month:02d}/{record.year} {record.property_type_id.name}"
                except (ValueError, AttributeError):
                    record.display_name = f"{record.month:02d}/{record.year} {record.property_type_id.name or 'Sans propriété'}"
            else:
                record.display_name = "Vue mensuelle incomplète"

    @api.depends('year', 'month', 'property_type_id')
    def _compute_reservation_stats(self):
        for record in self:
            if not record.year or not record.month or not record.property_type_id:
                record._reset_reservation_stats()
                continue

            # Rechercher toutes les réservations du mois
            reservations = record._get_month_reservations()

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

            reservations = record._get_month_reservations()

            record.total_revenue = sum(r.rate for r in reservations if r.rate)
            record.total_commission_booking = sum(r.commission_amount for r in reservations if r.commission_amount)
            record.total_tourist_tax = sum(r.tax_amount for r in reservations if r.tax_amount)

    @api.depends('total_revenue', 'total_commission_booking', 'total_tourist_tax', 'concierge_commission')
    def _compute_net_revenue(self):
        for record in self:
            record.net_revenue = (record.total_revenue -
                                  record.total_commission_booking -
                                  record.total_tourist_tax -
                                  record.concierge_commission)

    def action_generate_concierge_invoice(self):
        """Génère la facture concierge avec produit paramétrable"""
        self.ensure_one()

        # Vérifier le produit commission concierge
        if not self.concierge_service_id:
            raise ValueError(
                "Produit 'Commission conciergerie' introuvable! Veuillez créer un produit avec le code 'COMMISSION_CONCIERGE'.")

        if not self.concierge_partner_id:
            raise ValueError("Partenaire concierge introuvable!")

        if self.concierge_commission <= 0:
            raise ValueError("Aucune commission concierge à facturer pour cette période!")

        # Compte comptable depuis le produit
        account_id = self.concierge_service_id.product_tmpl_id._get_product_accounts()['expense']
        if not account_id:
            # Compte par défaut
            account_id = self.env['account.account'].search([
                ('code', '=', '62220000'),
                ('company_id', '=', self.env.user.company_id.id)
            ], limit=1)
            if not account_id:
                raise ValueError("Aucun compte comptable configuré pour les commissions!")

        # Journal de factures fournisseur
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.user.company_id.id)
        ], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé!")

        # Dates
        invoice_date = first_day_of_next_month(date(self.year, self.month, 1))
        invoice_date_due = fields.Date.add(invoice_date, days=30)

        # Référence de la facture
        ref = f"Commission concierge {self.month:02d}/{self.year}"

        # Vérifier si la facture existe déjà
        existing_invoice = self.env['account.move'].search([
            ('partner_id', '=', self.concierge_partner_id.id),
            ('ref', '=', ref),
            ('move_type', '=', 'in_invoice')
        ], limit=1)

        if existing_invoice:
            raise ValueError(f"Une facture existe déjà avec la référence: {ref}")

        # Supprimer l'ancienne facture liée si elle existe
        if self.concierge_invoice_id:
            old_invoice = self.concierge_invoice_id
            try:
                if old_invoice.state == 'posted':
                    old_invoice.button_draft()
                old_invoice.unlink()
            except Exception:
                pass
            self.concierge_invoice_id = False

        # Créer la ligne de facture
        invoice_lines = [(0, 0, {
            'product_id': self.concierge_service_id.id,
            'name': f"{self.concierge_service_id.name} {self.month:02d}/{self.year} {self.property_type_id.name} ({self.concierge_commission_rate}%)",
            'quantity': 1,
            'price_unit': round(self.concierge_commission, 2),
            'account_id': account_id.id,
            'tax_ids': [(6, 0, [])],
        })]

        # Créer la facture
        try:
            payment_term_30 = self.env.ref('account.account_payment_term_30days', raise_if_not_found=False)

            invoice_vals = {
                'partner_id': self.concierge_partner_id.id,
                'move_type': 'in_invoice',
                'invoice_date': invoice_date,
                'invoice_date_due': invoice_date_due,
                'ref': ref,
                'invoice_origin': f"Commission mensuelle Concierge - {self.month_name} {self.year}",
                'invoice_line_ids': invoice_lines,
                'journal_id': journal.id,
                'company_id': self.env.user.company_id.id,
                'currency_id': self.env.user.company_id.currency_id.id,
                'invoice_payment_term_id': payment_term_30.id if payment_term_30 else False,
            }

            invoice = self.env['account.move'].with_context(
                default_move_type='in_invoice',
                move_type='in_invoice'
            ).create(invoice_vals)

            self.concierge_invoice_id = invoice

            # Valider la facture
            invoice.action_post()

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
                'target': 'current',
            }

        except Exception as e:
            _logger.error(f"Erreur création facture concierge: {str(e)}")
            raise ValueError(f"Erreur lors de la création de la facture: {str(e)}")

    def action_generate_booking_invoice(self):
        """Génère les factures Booking.com avec produit paramétrable"""
        # Rechercher le produit commission Booking
        booking_service = self.env['product.product'].search([
            ('default_code', '=', 'COMMISSION_BOOKING'),
            '|', ('company_id', '=', self.env.user.company_id.id), ('company_id', '=', False)
        ], limit=1)

        if not booking_service:
            # Fallback : recherche par nom
            booking_service = self.env['product.product'].search([
                ('name', 'ilike', 'commission booking'),
                '|', ('company_id', '=', self.env.user.company_id.id), ('company_id', '=', False)
            ], limit=1)

        # Compte comptable
        if booking_service:
            account_id = booking_service.product_tmpl_id._get_product_accounts()['expense']
        else:
            account_id = None

        if not account_id:
            account_id = self.env['account.account'].search([('code', '=', '62220000')], limit=1)
            if not account_id:
                raise ValueError("Le compte de charge '62220000' n'existe pas.")

        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.env.user.company_id.id)
        ], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé.")

        partner_booking = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)
        if not partner_booking:
            raise ValueError("Le partenaire 'Booking.com' n'existe pas!")

        # Traiter les réservations du mois
        reservations = self._get_month_reservations()

        # Regroupement par mois d'arrivée
        factures_groupees = {}

        for reservation in reservations:
            if not reservation.arrival_date:
                continue

            month = reservation.arrival_date.month
            year = reservation.arrival_date.year
            key = (year, month)

            # Commission Booking
            commission = getattr(reservation, 'commission_amount', 0)
            try:
                montant = float(str(commission).replace(',', '').replace(' XPF', ''))
            except Exception:
                continue

            if montant > 0:
                line_data = {
                    'name': f"{reservation.property_type_id.name} {reservation.arrival_date.strftime('%d/%m/%Y')}",
                    'quantity': 1,
                    'price_unit': montant,
                    'account_id': account_id.id,
                }

                # Ajouter le produit si disponible
                if booking_service:
                    line_data['product_id'] = booking_service.id

                facture_line = (0, 0, line_data)

                # Date de facture (premier jour du mois suivant)
                invoice_date = first_day_of_next_month(reservation.arrival_date)
                invoice_date_due = fields.Date.add(invoice_date, days=15)

                ref = f"Commission plateforme {month:02d}/{year}"

                factures_groupees.setdefault(key, {
                    'partner_id': partner_booking.id,
                    'invoice_date': invoice_date,
                    'invoice_date_due': invoice_date_due,
                    'ref': ref,
                    'invoice_line_ids': [],
                })['invoice_line_ids'].append(facture_line)

        # Créer les factures
        created_invoices = []
        for key, vals in factures_groupees.items():
            # Vérifier si la facture existe déjà
            existing = self.env['account.move'].search([
                ('partner_id', '=', vals['partner_id']),
                ('ref', '=', vals['ref']),
                ('move_type', '=', 'in_invoice')
            ], limit=1)

            if not existing:
                try:
                    payment_term_30 = self.env.ref('account.account_payment_term_30days', raise_if_not_found=False)

                    invoice = self.env['account.move'].create({
                        'move_type': 'in_invoice',
                        'partner_id': vals['partner_id'],
                        'invoice_date': vals['invoice_date'],
                        'invoice_date_due': vals['invoice_date_due'],
                        'ref': vals['ref'],
                        'invoice_origin': "Commission mensuelle Booking",
                        'invoice_line_ids': vals['invoice_line_ids'],
                        'journal_id': journal.id,
                        'company_id': self.env.user.company_id.id,
                        'invoice_payment_term_id': payment_term_30.id if payment_term_30 else False,
                    })

                    # Lier la facture au mois correspondant
                    if key == (self.year, self.month):
                        self.booking_invoice_id = invoice

                    invoice.action_post()
                    created_invoices.append(invoice.id)

                except Exception as e:
                    _logger.error(f"Erreur création facture Booking: {str(e)}")

        return len(created_invoices)

    @api.model
    def create_or_update_month(self, property_type_id, year, month, company_id=None):
        """
        Crée ou met à jour un enregistrement BookingMonth pour la période donnée.
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
        property_type = property_type_id if hasattr(property_type_id, 'exists') else self.env[
            'product.template'].browse(property_type_id)
        if not property_type.exists():
            raise ValueError(f"Type d'hébergement inexistant: {property_type_id}")

        # Vérifier que la société existe
        company = company_id if hasattr(company_id, 'exists') else self.env['res.company'].browse(company_id)
        if not company.exists():
            raise ValueError(f"Société inexistante: {company_id}")

        # Rechercher un enregistrement existant
        domain = [
            ('year', '=', year),
            ('month', '=', month),
            ('property_type_id', '=', property_type_id.id if hasattr(property_type_id, 'id') else property_type_id),
            ('company_id', '=', company_id)
        ]

        existing_record = self.search(domain, limit=1)

        if existing_record:
            # Mettre à jour l'enregistrement existant
            existing_record.action_recalculate()
            return existing_record
        else:
            # Créer un nouvel enregistrement
            values = {
                'year': year,
                'month': month,
                'property_type_id': property_type_id.id if hasattr(property_type_id, 'id') else property_type_id,
                'company_id': company_id,
            }

            new_record = self.create(values)
            return new_record

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

    @api.depends('property_type_id', 'company_id')
    def _compute_concierge_service(self):
        """Récupère le produit et le taux de commission conciergerie"""
        for record in self:
            # Rechercher le produit "Commission conciergerie"
            concierge_service = record._get_service_product('COMMISSION_CONCIERGE')

            if concierge_service:
                record.concierge_service_id = concierge_service
                # Récupérer le taux depuis la liste de prix du concierge
                concierge_partner = record.concierge_partner_id
                # concierge_partner = record._get_concierge_partner()
                if concierge_partner and concierge_partner.property_product_pricelist:
                    # Le prix du service représente le pourcentage (ex: 20.0 pour 20%)
                    rate = concierge_service._get_price_in_pricelist(
                        concierge_partner.property_product_pricelist
                    )
                    record.concierge_commission_rate = rate if rate else concierge_service.list_price
                else:
                    record.concierge_commission_rate = concierge_service.list_price
            else:
                record.concierge_service_id = False
                record.concierge_commission_rate = 20.0  # Valeur par défaut 20%
                _logger.warning(f"Produit 'Commission conciergerie' introuvable pour {record.display_name}")

    @api.depends('company_id')
    def _compute_booking_service(self):
        """Récupère le produit pour les commissions Booking.com"""
        for record in self:
            booking_service = record._get_service_product('COMMISSION_BOOKING')
            record.booking_service_id = booking_service

    @api.depends('year', 'month', 'property_type_id')
    def _compute_reservation_stats(self):
        """Calcule les statistiques des réservations"""
        for record in self:
            if not record._is_valid_period():
                record._reset_reservation_stats()
                continue

            reservations = record._get_month_reservations()

            record.total_reservations = len(reservations)
            # record.reservation_count = len(reservations)

            if reservations:
                # Calculs de base
                record.total_nights = sum(r.total_nights for r in reservations if r.total_nights)
                record.total_guests = sum(r.pax_nb for r in reservations if r.pax_nb)

                # Durée moyenne de séjour
                stays = [r.duration_nights for r in reservations if r.duration_nights]
                record.average_stay = sum(stays) / len(stays) if stays else 0.0

                # Tarif moyen
                rates = [r.rate for r in reservations if r.rate]
                record.average_rate = sum(rates) / len(rates) if rates else 0.0
            else:
                record.total_nights = 0
                record.total_guests = 0
                record.average_stay = 0.0
                record.average_rate = 0.0

    @api.depends('year', 'month', 'property_type_id')
    def _compute_financial_data(self):
        """Calcule les données financières de base"""
        for record in self:
            if not record._is_valid_period():
                record._reset_financial_data()
                continue

            reservations = record._get_month_reservations()

            # Calculs financiers de base
            record.total_revenue = sum(r.rate for r in reservations if r.rate)
            record.total_commission_booking = sum(r.commission_amount for r in reservations if r.commission_amount)
            record.total_tourist_tax = sum(r.tax_amount for r in reservations if r.tax_amount)

    @api.depends('year', 'month', 'property_type_id')
    def _compute_channel_revenue(self):
        """Calcule les revenus par canal de distribution"""
        for record in self:
            if not record._is_valid_period():
                record.revenue_booking_com = 0.0
                record.revenue_direct = 0.0
                record.revenue_other_channels = 0.0
                continue

            reservations = record._get_month_reservations()

            # Répartition par canal (basée sur des critères à adapter)
            booking_revenue = 0.0
            direct_revenue = 0.0
            other_revenue = 0.0

            for reservation in reservations:
                if reservation.rate:
                    # Logique de classification des canaux
                    if hasattr(reservation, 'channel') and reservation.channel:
                        if 'booking' in reservation.channel.lower():
                            booking_revenue += reservation.rate
                        elif 'direct' in reservation.channel.lower():
                            direct_revenue += reservation.rate
                        else:
                            other_revenue += reservation.rate
                    else:
                        # Par défaut, considérer comme Booking.com si commission présente
                        if reservation.commission_amount:
                            booking_revenue += reservation.rate
                        else:
                            direct_revenue += reservation.rate

            record.revenue_booking_com = booking_revenue
            record.revenue_direct = direct_revenue
            record.revenue_other_channels = other_revenue

    @api.depends('concierge_commission_base', 'total_tourist_tax', 'concierge_commission_rate')
    def _compute_partner_commissions(self):
        """Calcule les commissions des partenaires"""
        for record in self:
            commission_base = max(0.0, record.concierge_commission_base - record.total_tourist_tax) or 0.0

            # Commission concierge
            record.concierge_commission = commission_base * record.concierge_commission_rate / 100.0 or 0.0

    @api.depends('total_revenue', 'total_commission_booking', 'total_tourist_tax',
                 'concierge_commission')
    def _compute_net_revenue(self):
        """Calcule les revenus nets et marges"""
        for record in self:
            record.gross_revenue = record.total_revenue

            # Coûts totaux
            record.total_costs = (record.total_commission_booking +
                                  record.total_tourist_tax +
                                  record.concierge_commission)

            # Revenu net
            record.net_revenue = record.gross_revenue - record.total_costs

            # Marge bénéficiaire
            if record.gross_revenue > 0:
                record.profit_margin = (record.net_revenue / record.gross_revenue) * 100
            else:
                record.profit_margin = 0.0

    @api.depends('booking_invoice_id', 'concierge_invoice_id', 'tourist_tax_invoice_id')
    def _compute_invoice_state(self):
        """Calcule l'état de facturation"""
        for record in self:
            invoices_expected = []
            invoices_created = []

            # Facture Booking.com
            if record.total_commission_booking > 0:
                invoices_expected.append('booking')
                if record.booking_invoice_id:
                    invoices_created.append('booking')

            # Facture concierge
            if record.concierge_commission > 0:
                invoices_expected.append('concierge')
                if record.concierge_invoice_id:
                    invoices_created.append('concierge')

            # Facture taxe de séjour (si applicable)
            if record.total_tourist_tax > 0:
                invoices_expected.append('tourist_tax')
                if record.tourist_tax_invoice_id:
                    invoices_created.append('tourist_tax')

            # Déterminer l'état
            if not invoices_expected:
                record.invoice_state = 'none'
            elif len(invoices_created) == len(invoices_expected):
                record.invoice_state = 'complete'
            elif invoices_created:
                record.invoice_state = 'partial'
            else:
                record.invoice_state = 'none'

    # ========================================
    # MÉTHODES UTILITAIRES
    # ========================================

    def _is_valid_period(self):
        """Vérifie si la période est valide"""
        return self.year and self.month and self.property_type_id

    def _get_service_product(self, code):
        """Récupère un produit de service par code"""
        return self.env['product.product'].search([
            ('default_code', '=', code),
            '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False)
        ], limit=1)

    def _get_month_reservations(self):
        """Récupère toutes les réservations du mois pour cette propriété"""
        if not self.period_start or not self.period_end:
            return self.env['booking.import.line']

        return self.env['booking.import.line'].search([
            ('property_type_id', '=', self.property_type_id.id),
            ('arrival_date', '>=', self.period_start),
            ('arrival_date', '<=', self.period_end),
            ('status', '=', 'ok')  # Seules les réservations confirmées
        ])

    def _reset_reservation_stats(self):
        """Remet à zéro les statistiques de réservations"""
        self.total_reservations = 0
        self.total_nights = 0
        self.total_guests = 0
        self.average_stay = 0.0
        self.average_rate = 0.0
        # self.reservation_count = 0

    def _reset_financial_data(self):
        """Remet à zéro les données financières"""
        self.total_revenue = 0.0
        self.total_commission_booking = 0.0
        self.total_tourist_tax = 0.0
        self.revenue_booking_com = 0.0
        self.revenue_direct = 0.0
        self.revenue_other_channels = 0.0

    # ========================================
    # MÉTHODES D'ACTION
    # ========================================

    def action_recalculate(self):
        """Force le recalcul des données avec mise à jour des métadonnées"""
        for record in self:
            # Marquer comme en cours de calcul
            record.state = 'draft'

            # Forcer le recalcul de tous les champs computed
            record._compute_reservation_stats()
            record._compute_financial_data()
            record._compute_channel_revenue()
            record._compute_concierge_service()
            record._compute_partner_commissions()
            # record._compute_additional_commissions()
            record._compute_net_revenue()
            record._compute_invoice_state()

            # Mettre à jour les métadonnées
            record.write({
                'last_calculation_date': fields.Datetime.now(),
                'calculation_user_id': self.env.user.id,
                'state': 'calculated'
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recalcul terminé',
                'message': f'{len(self)} vue(s) mensuelle(s) recalculée(s)',
                'type': 'success',
            }
        }

    def action_validate(self):
        """Valide la vue mensuelle"""
        for record in self:
            if record.state not in ['calculated', 'validated']:
                raise UserError("La vue doit être calculée avant d'être validée.")
            record.state = 'validated'
        return True

    def action_reset_to_draft(self):
        """Remet en brouillon"""
        for record in self:
            record.state = 'draft'
        return True

    @api.depends('year', 'month')
    def _compute_days_in_month(self):
        """Calcule le nombre de jours dans le mois"""
        for record in self:
            if record.year and record.month:
                try:
                    if record.month == 12:
                        next_month = datetime(record.year + 1, 1, 1)
                    else:
                        next_month = datetime(record.year, record.month + 1, 1)
                    current_month = datetime(record.year, record.month, 1)
                    days_count = (next_month - current_month).days
                    # Pas de champ days_in_month défini, on peut l'ignorer ou l'utiliser dans les calculs
                except ValueError:
                    days_count = 30  # Valeur par défaut
            else:
                days_count = 30

    def _compute_reservations(self):
        """Calcule la liste des réservations (pour affichage)"""
        for record in self:
            # Cette méthode peut rester vide si reservation_ids n'est pas défini
            pass

    @api.depends('reservation_ids')
    def _compute_reservation_count(self):
        """Calcule le nombre de réservations"""
        for record in self:
            # Si reservation_ids n'existe pas, utiliser une autre méthode
            reservations = record._get_month_reservations()
            # Pas de champ reservation_count défini, on peut l'ignorer ou l'utiliser localement

    @api.depends('total_nights', 'property_type_id')  # Suppression de days_in_month
    def _compute_occupancy_stats(self):
        """Calcule les statistiques d'occupation"""
        for record in self:
            if record.year and record.month and record.property_type_id:
                # Calculer le nombre de jours dans le mois
                try:
                    if record.month == 12:
                        next_month = datetime(record.year + 1, 1, 1)
                    else:
                        next_month = datetime(record.year, record.month + 1, 1)
                    current_month = datetime(record.year, record.month, 1)
                    days_in_month = (next_month - current_month).days

                    # Capacité théorique (approximative)
                    theoretical_capacity = days_in_month  # Simplifié : 1 unité par jour
                    if record.total_nights > 0 and theoretical_capacity > 0:
                        occupancy_rate = (record.total_nights / theoretical_capacity) * 100
                    else:
                        occupancy_rate = 0.0
                except ValueError:
                    occupancy_rate = 0.0
            else:
                occupancy_rate = 0.0

    def action_generate_concierge_client_invoice(self):
        """Génère la facture client chez le fournisseur concierge"""
        self.ensure_one()

        # Vérifications préalables
        if not self.concierge_invoice_id:
            raise ValueError("La facture fournisseur doit être créée avant la facture client!")

        if not self.concierge_partner_id:
            raise ValueError("Partenaire concierge introuvable!")

        if not self.concierge_service_id:
            raise ValueError("Produit 'Commission conciergerie' introuvable!")

        if self.concierge_commission <= 0:
            raise ValueError("Aucune commission concierge à facturer pour cette période!")

        # Récupérer la société du concierge
        concierge_company = self.env['res.company'].search([
            ('partner_id', '=', self.concierge_partner_id.id)
        ], limit=1)

        # 3. Chercher par nom si le partenaire concierge est partagé
        if not concierge_company:
            concierge_company = self.env['res.company'].search([
                ('name', '=', self.concierge_partner_id.name)
            ], limit=1)

        if not concierge_company:
            raise ValueError(
                "Impossible de déterminer la société du concierge! Vérifiez la configuration du partenaire concierge.")

        # Basculer vers la société du concierge
        current_company = self.env.user.company_id

        try:
            # Créer la facture dans la société du concierge
            invoice_vals = self._prepare_concierge_client_invoice_vals(concierge_company, current_company)

            # Exécuter dans le contexte de la société concierge
            concierge_invoice = self.with_context(
                allowed_company_ids=[concierge_company.id],
                force_company=concierge_company.id
            ).sudo().env['account.move'].create(invoice_vals)

            # Sauvegarder la référence
            self.concierge_client_invoice_id = concierge_invoice

            # Valider la facture client
            concierge_invoice.action_post()

            return {
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': concierge_invoice.id,
                'target': 'new',
                'context': {
                    'allowed_company_ids': [concierge_company.id],
                    'force_company': concierge_company.id
                }
            }

        except Exception as e:
            raise ValueError(f"Erreur lors de la création de la facture client: {str(e)}")

    def _prepare_concierge_client_invoice_vals(self, concierge_company, client_company):
        """Prépare les valeurs pour la facture client concierge"""

        # Rechercher le produit commission (partagé ou spécifique à la société concierge)
        concierge_service = self.env['product.product'].search([
            ('default_code', '=', 'COMMISSION_CONCIERGE'),
            '|',
            ('company_id', '=', concierge_company.id),
            ('company_id', '=', False)  # Produit partagé entre toutes les sociétés
        ], limit=1)

        if not concierge_service:
            # Utiliser le même produit que dans la facture fournisseur s'il est partagé
            if self.concierge_service_id.company_id in (False, concierge_company):
                concierge_service = self.concierge_service_id
            else:
                # Créer le produit s'il n'existe pas
                concierge_service = self._create_concierge_service_product(concierge_company)

        # Compte comptable depuis le produit dans la société concierge
        accounts = concierge_service.product_tmpl_id.with_company(concierge_company.id)._get_product_accounts()
        account_id = accounts.get('income')

        if not account_id:
            # Compte par défaut dans la société concierge
            account_id = self.sudo().env['account.account'].search([
                ('code', '=like', '7%'),
                ('account_type', '=', 'income'),
                ('company_id', '=', concierge_company.id)
            ], limit=1)

        if not account_id:
            raise ValueError("Aucun compte comptable de vente configuré dans la société concierge!")

        # Journal de ventes dans la société concierge
        journal = self.sudo().env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', concierge_company.id)
        ], limit=1)

        if not journal:
            raise ValueError("Aucun journal de vente trouvé dans la société concierge!")

        # Partenaire client : rechercher le partenaire de la société cliente
        # Il peut être partagé (company_id = False) ou spécifique
        client_partner = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('name', '=', client_company.name),
            '|',
            ('company_id', '=', concierge_company.id),
            ('company_id', '=', False)  # Partenaire partagé
        ], limit=1)

        if not client_partner:
            # Créer le partenaire client dans la société concierge si nécessaire
            client_partner = self._create_client_partner(client_company, concierge_company)

        # Dates
        invoice_date = first_day_of_next_month(date(self.year, self.month, 1))
        invoice_date_due = fields.Date.add(invoice_date, days=30)

        # Référence de la facture
        ref = f"Commission concierge {self.month:02d}/{self.year}"

        # Vérifier si la facture existe déjà
        existing_invoice = self.sudo().env['account.move'].search([
            ('partner_id', '=', client_partner.id),
            ('ref', '=', ref),
            ('move_type', '=', 'out_invoice'),
            ('company_id', '=', concierge_company.id)
        ], limit=1)

        if existing_invoice:
            raise ValueError(f"Une facture client existe déjà avec la référence: {ref}")

        # Ligne de facture
        invoice_lines = [(0, 0, {
            'product_id': concierge_service.id,
            'name': f"{self.concierge_service_id.name} {self.month:02d}/{self.year} {self.property_type_id.name} ({self.concierge_commission_rate}%)",
            'quantity': 1,
            'price_unit': round(self.concierge_commission, 2),
            'account_id': account_id.id,
            'tax_ids': self._get_concierge_taxes(concierge_company, client_partner, concierge_service),
        })]

        # Conditions de paiement
        payment_term_30 = self.env.ref('account.account_payment_term_30days', raise_if_not_found=False)

        # Déterminer la position fiscale pour la facture
        fiscal_position = None
        if client_partner.property_account_position_id:
            fiscal_position = client_partner.property_account_position_id
        else:
            w_fiscal_position = self.sudo().env['account.fiscal.position'].with_company(concierge_company.id)
            fiscal_position = w_fiscal_position._get_fiscal_position(partner=client_partner)

        return {
            'partner_id': client_partner.id,
            'move_type': 'out_invoice',
            'invoice_date': invoice_date,
            'invoice_date_due': invoice_date_due,
            'ref': ref,
            'invoice_origin': f"Commission mensuelle Concierge - {self.month_name} {self.year}",
            'invoice_line_ids': invoice_lines,
            'journal_id': journal.id,
            'company_id': concierge_company.id,
            'currency_id': concierge_company.currency_id.id,
            'invoice_payment_term_id': payment_term_30.id if payment_term_30 else False,
            'fiscal_position_id': fiscal_position.id if fiscal_position else False,
        }

    def _create_client_partner(self, client_company, concierge_company):
        """Crée le partenaire client dans la société concierge"""
        partner_vals = {
            'name': client_company.name,
            'is_company': True,
            'customer_rank': 1,
            'supplier_rank': 0,
            'company_id': False,  # Créer comme partenaire partagé
            'street': client_company.street,
            'street2': client_company.street2,
            'city': client_company.city,
            'zip': client_company.zip,
            'country_id': client_company.country_id.id if client_company.country_id else False,
            'phone': client_company.phone,
            'email': client_company.email,
            'vat': client_company.vat,
        }

        return self.env['res.partner'].create(partner_vals)

    def _create_concierge_service_product(self, concierge_company):
        """Crée le produit commission concierge partagé entre les sociétés"""

        # Catégorie de produits services (recherche partagée)
        service_category = self.env['product.category'].search([
            ('name', '=', 'Services'),
            '|',
            ('company_id', '=', concierge_company.id),
            ('company_id', '=', False)
        ], limit=1)

        if not service_category:
            service_category = self.env['product.category'].search([
                ('company_id', '=', False)  # Catégorie partagée
            ], limit=1)

        product_vals = {
            'name': 'Commission concierge',
            'default_code': 'COMMISSION_CONCIERGE',
            'type': 'service',
            'categ_id': service_category.id if service_category else False,
            'sale_ok': True,
            'purchase_ok': True,  # Permet l'achat et la vente
            'company_id': False,  # Produit partagé entre toutes les sociétés
        }

        return self.env['product.product'].create(product_vals)

    def _get_concierge_taxes(self, concierge_company, client_partner, concierge_service):
        """Récupère les taxes applicables dans la société concierge en tenant compte de la position fiscale"""

        # 1. Déterminer la position fiscale du client
        fiscal_position = None

        # Position fiscale spécifique du partenaire
        if client_partner.property_account_position_id:
            fiscal_position = client_partner.property_account_position_id
        else:
            w_fiscal_position = self.sudo().env['account.fiscal.position'].with_company(concierge_company.id)
            fiscal_position = w_fiscal_position._get_fiscal_position(partner=client_partner)

        # 2. Récupérer les taxes par défaut du produit
        product_taxes = concierge_service.taxes_id.filtered(
            lambda t: t.company_id == concierge_company
        )

        # Si pas de taxes sur le produit, prendre les taxes de vente par défaut
        if not product_taxes:
            product_taxes = self.sudo().env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', concierge_company.id),
                ('active', '=', True)
            ], limit=1)

        # 3. Appliquer la position fiscale si elle existe
        if fiscal_position and product_taxes:
            # Mapper les taxes selon la position fiscale
            mapped_taxes = fiscal_position.map_tax(product_taxes)
            return [(6, 0, mapped_taxes.ids)] if mapped_taxes else [(6, 0, [])]

        # 4. Retourner les taxes du produit ou taxes par défaut
        if product_taxes:
            return [(6, 0, product_taxes.ids)]
        else:
            return [(6, 0, [])]  # Pas de taxes

    def action_generate_both_concierge_invoices(self):
        """Génère les deux factures : fournisseur (société cliente) et client (société concierge)"""
        # Créer d'abord la facture fournisseur
        airbnb_vendor_ok = self.origin == 'airbnb' and self.company_id.hm_airbnb_vendor_concierge_commission
        booking_vendor_ok = self.origin == 'booking.com' and self.company_id.hm_booking_vendor_concierge_commission
        if airbnb_vendor_ok or booking_vendor_ok:
            self.action_generate_concierge_invoice()

        # Puis créer la facture client
        airbnb_customer_ok = self.origin == 'airbnb' and self.company_id.hm_airbnb_customer_concierge_commission
        booking_customer_ok = self.origin == 'booking.com' and self.company_id.hm_booking_customer_concierge_commission
        if airbnb_customer_ok or booking_customer_ok:
            self.action_generate_concierge_client_invoice()
        return

    def _get_fiscal_position_manual(self, partner, company):
        """Recherche manuelle de la position fiscale appropriée"""

        # Rechercher les positions fiscales de la société concierge
        fiscal_positions = self.sudo().env['account.fiscal.position'].search([
            ('company_id', '=', company.id),
            ('auto_apply', '=', True)
        ])

        # Logique de sélection basée sur le pays et l'état
        for fp in fiscal_positions:
            # Position fiscale par pays
            if fp.country_id and partner.country_id:
                if fp.country_id == partner.country_id:
                    # Vérifier l'état si spécifié
                    if fp.state_ids:
                        if partner.state_id and partner.state_id in fp.state_ids:
                            return fp
                    else:
                        # Pas d'état spécifié, le pays suffit
                        return fp

            # Position fiscale par groupe de pays
            elif fp.country_group_id and partner.country_id:
                if partner.country_id in fp.country_group_id.country_ids:
                    return fp

        # Aucune position fiscale trouvée
        return None

    @api.depends('year', 'month', 'property_type_id', 'company_id')
    def _compute_base_concierge_commission(self):
        """
        Calcule la base de commission concierge en cumulant les montants
        des lignes d'import pour le mois, l'année, le type de propriété et la société donnés
        """
        for record in self:
            # Initialiser le montant
            total_commission = 0.0

            if record.year and record.month and record.property_type_id and record.company_id:
                # Définir les dates de début et fin du mois
                start_date = date(record.year, record.month, 1)

                # Calculer le dernier jour du mois
                if record.month == 12:
                    end_date = date(record.year + 1, 1, 1)
                else:
                    end_date = date(record.year, record.month + 1, 1)

                # Rechercher les lignes d'import correspondantes
                domain = [
                    ('arrival_date', '>=', start_date),
                    ('arrival_date', '<', end_date),
                    ('property_type_id', '=', record.property_type_id.id),
                    ('company_id', '=', record.company_id.id),
                    ('status', '=', 'ok'),  # Seulement les réservations confirmées
                ]

                # Rechercher les lignes dans le modèle booking.import.line
                import_lines = self.env['booking.import.line'].search(domain)

                # Sommer les commissions
                for line in import_lines:
                    if line.base_concierge_commission:
                        total_commission += line.base_concierge_commission

            record.concierge_commission_base = total_commission

    @api.model
    def recalculate_all_commissions(self):
        """
        Méthode utilitaire pour recalculer toutes les commissions
        Peut être appelée manuellement ou par un cron
        """
        all_records = self.search([])
        all_records._compute_base_concierge_commission()
        return True

    def action_recalculate_commission(self):
        """
        Action pour recalculer la commission depuis l'interface
        """
        self._compute_base_concierge_commission()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recalcul terminé',
                'message': f'Commission recalculée: {self.concierge_commission_base:.2f}',
                'type': 'success',
            }
        }

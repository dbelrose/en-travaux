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
                                           compute='_compute_partner_info', store=True)

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
    def _compute_partner_info(self):
        for record in self:
            # Récupérer le partenaire concierge depuis la société de la propriété
            if record.property_type_id and record.property_type_id.company_id:
                # Le concierge est le partenaire lié à la société de la propriété
                record.concierge_partner_id = record.property_type_id.company_id.partner_id
            else:
                record.concierge_partner_id = False

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

    def action_generate_municipality_invoice(self):
        municipality = self.env['res.partner'].search([('name', '=', 'Mairie de Punaauia')], limit=1)
        if not municipality:
            raise ValueError("Le fournisseur 'Mairie de Punaauia' n'existe pas !")

        account_id = self.env['account.account'].search([('code', '=', '63513000'),
                                                         ('company_id', '=', self.env.user.company_id.id)], limit=1).id
        if not account_id:
            raise ValueError("Le compte comptable '63513000' n'existe pas !")

        bookings = self.search([])
        # bookings = self.env['booking.import'].search([])

        invoices_by_ref = {}

        for booking in bookings:
            trimestre = ((booking.month - 1) // 3) + 1
            ref = f"{booking.property_type_id.name}-{booking.year}-T{trimestre}"
            label = f"Taxe de séjour T{trimestre} {booking.year} - {booking.property_type_id.name}"

            # Chercher la facture existante (même ref + même partenaire)
            existing_invoice = self.env['account.move'].search([
                ('partner_id', '=', municipality.id),
                ('ref', '=', ref),
                ('move_type', '=', 'in_invoice')
            ], limit=1)

            invoice_date = fields.Date.today()
            invoice_date_due = fields.Date.add(invoice_date, days=30)  # Échéance à 30 jours

            invoice_vals = {
                'partner_id': municipality.id,
                'move_type': 'in_invoice',
                'invoice_date': invoice_date,
                'invoice_date_due': invoice_date_due,  # AJOUT DE LA DATE D'ÉCHÉANCE
                'ref': ref,
                'state': 'draft',
                'invoice_line_ids': [],
            }

            # Identifier les mois déjà facturés (via le nom des lignes)
            mois_factures = set()
            if existing_invoice:
                for line in existing_invoice.invoice_line_ids:
                    for i in range(1, 4):
                        mois_key = f"- Trimestre {i}"
                        if mois_key in line.name and booking.property_type_id.name in line.name:
                            mois_factures.add(i)

            # Ajouter les nouvelles lignes (mois non encore facturés)
            for i in range(1, 4):
                if i in mois_factures:
                    continue  # ligne déjà facturée

                champ = f'nuitees_mois{i}'
                try:
                    qty = int(booking[champ] or 0)
                except (ValueError, TypeError):
                    qty = 0

                if qty > 0:
                    line_vals = (0, 0, {
                        'name': f"{label} - Mois {i}",
                        'quantity': qty,
                        'price_unit': 60.0,
                        'account_id': account_id,
                    })
                    invoice_vals['invoice_line_ids'].append(line_vals)

            if not invoice_vals['invoice_line_ids']:
                continue  # rien à ajouter

            if existing_invoice:
                if existing_invoice.state != 'draft':
                    existing_invoice.button_draft()
                # Mise à jour de la date d'échéance aussi
                existing_invoice.write({
                    'invoice_line_ids': invoice_vals['invoice_line_ids'],
                    'invoice_date_due': invoice_date_due
                })
                invoice = existing_invoice
            else:
                invoice = self.env['account.move'].create(invoice_vals)

            invoice.action_post()

        return True

    def action_generate_concierge_invoice(self):
        # Compte de charge pour commissions
        account_id = self.env['account.account'].search([('code', '=', '62220000'),
                                                         ('company_id', '=', self.env.user.company_id.id)], limit=1)
        if not account_id:
            raise ValueError("Le compte de charge '62220000' n'existe pas.")

        journal = self.env['account.journal'].search([('code', '=', 'FACTU')], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé.")

        current_company = self.env.user.company_id
        all_lines = self.env['booking.import.line'].search([])

        # Regroupement des lignes par propriété + mois d'arrivée
        factures_groupees = {}

        for line in all_lines:
            if not line.property_type_id or not line.arrival_date:
                continue

            # Informations de regroupement
            property_type = line.property_type_id
            month = line.arrival_date.month
            year = line.arrival_date.year
            key = (year, month)

            # Informations de facturation
            tarif = getattr(line, 'rate', 0)
            commission = getattr(line, 'commission_amount', 0)

            try:
                tarif = float(str(tarif).replace(',', '').replace(' XPF', ''))
                commission = float(str(commission).replace(',', '').replace(' XPF', ''))
            except Exception:
                continue

            nb_adultes = (line.pax_nb or 0) - (line.children or 0)
            nuitees = (line.duration_nights or 0) * nb_adultes
            taxe_sejour = nuitees * 60

            base = tarif - commission - taxe_sejour
            if base <= 0:
                continue

            montant = round(base * 0.20, 0)

            facture_line = (0, 0, {
                'name': f"Commission {property_type.name} - {line.arrival_date.strftime('%d/%m/%Y')}",
                'quantity': 1,
                'price_unit': montant,
                'account_id': account_id.id,
                'product_uom_id': self.env.ref('uom.product_uom_unit').id,
            })

            invoice_date = fields.Date.today()
            invoice_date_due = fields.Date.add(invoice_date, days=30)  # Échéance à 30 jours

            factures_groupees.setdefault(key, {
                'partner_id': property_type.company_id.partner_id.user_id.company_id.partner_id.id,
                'invoice_date': invoice_date,
                'invoice_date_due': invoice_date_due,  # AJOUT DE LA DATE D'ÉCHÉANCE
                'ref': f"Commission {property_type.company_id.name} - {month:02d}/{year}",
                'invoice_line_ids': [],
            })['invoice_line_ids'].append(facture_line)

        created_invoices = []

        for key, vals in factures_groupees.items():
            if not self.env['account.move'].search([
                ('partner_id', '=', vals['partner_id']),
                ('ref', '=', vals['ref']),
                ('move_type', '=', 'in_invoice')
            ], limit=1):
                invoice = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'partner_id': vals['partner_id'],
                    'invoice_date': vals['invoice_date'],
                    'invoice_date_due': vals['invoice_date_due'],  # AJOUT DE LA DATE D'ÉCHÉANCE
                    'ref': vals['ref'],
                    'invoice_origin': "Commissions mensuelles Booking",
                    'invoice_line_ids': vals['invoice_line_ids'],
                    'journal_id': journal.id,
                    'company_id': current_company.id,
                })
                created_invoices.append(invoice.id)

    def action_generate_booking_invoice(self):
        # Compte de charge pour commissions
        account_id = self.env['account.account'].search([('code', '=', '62220000')], limit=1)
        if not account_id:
            raise ValueError("Le compte de charge '62220000' n'existe pas.")

        journal = self.env['account.journal'].search([('code', '=', 'FACTU')], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé.")

        current_company = self.env.user.company_id
        all_lines = self.env['booking.import.line'].search([])

        # Regroupement des lignes par propriété + mois d'arrivée
        factures_groupees = {}

        partner_id = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)

        for line in all_lines:
            if not line.property_type_id or not line.arrival_date:
                continue

            # Informations de regroupement
            month = line.arrival_date.month
            year = line.arrival_date.year
            key = (year, month)

            # Informations de facturation
            commission = getattr(line, 'commission_amount', 0)

            try:
                montant = float(str(commission).replace(',', '').replace(' XPF', ''))
            except Exception:
                continue

            if montant > 0:
                facture_line = (0, 0, {
                    'name': f"Commission {line.property_type_id.name} - {line.arrival_date.strftime('%d/%m/%Y')}",
                    'quantity': 1,
                    'price_unit': montant,
                    'account_id': account_id.id,
                    'product_uom_id': self.env.ref('uom.product_uom_unit').id,
                })

                # Calculer la date d'échéance (premier jour du mois suivant + 30 jours)
                invoice_date = first_day_of_next_month(line.arrival_date)
                invoice_date_due = fields.Date.add(invoice_date, days=30)

                factures_groupees.setdefault(key, {
                    'partner_id': partner_id.id,
                    'invoice_date': invoice_date,
                    'invoice_date_due': invoice_date_due,  # AJOUT DE LA DATE D'ÉCHÉANCE
                    'ref': f"Commission {line.property_type_id.company_id.name} - {month:02d}/{year}",
                    'invoice_line_ids': [],
                })['invoice_line_ids'].append(facture_line)

        created_invoices = []

        for key, vals in factures_groupees.items():
            if not self.env['account.move'].search([
                ('partner_id', '=', vals['partner_id']),
                ('ref', '=', vals['ref']),
                ('move_type', '=', 'in_invoice')
            ], limit=1):
                invoice = self.env['account.move'].create({
                    'move_type': 'in_invoice',
                    'partner_id': vals['partner_id'],
                    'invoice_date': vals['invoice_date'],
                    'invoice_date_due': vals['invoice_date_due'],  # AJOUT DE LA DATE D'ÉCHÉANCE
                    'ref': vals['ref'],
                    'invoice_origin': "Commissions mensuelles Booking",
                    'invoice_line_ids': vals['invoice_line_ids'],
                    'journal_id': journal.id,
                    'company_id': current_company.id,
                })
                created_invoices.append(invoice.id)

    def action_generate_all_invoices(self):
        self.action_generate_booking_invoice()
        self.action_generate_concierge_invoice()
        self.action_generate_municipality_invoice()

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
            ('property_type_id', '=', property_type_id.id),
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
            existing_record._compute_partner_info()
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

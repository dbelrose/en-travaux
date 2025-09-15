# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pandas as pd
import base64
import io
import logging

_logger = logging.getLogger(__name__)


def count_integers_leq_12(s):
    """Fonction pour compter les entiers inférieurs ou égaux à 12"""
    if not s or s == '':
        return 0
    numbers = s.split(', ')
    count = sum(1 for num in numbers
                if num.strip() and num.strip().isdigit()
                and int(num.strip()) <= 12)
    return count


class BookingImport(models.Model):
    _name = 'booking.import'
    _description = 'Import de fichier de réservations Booking.com'
    _order = 'import_date desc'
    _rec_name = 'display_name'

    # Identification de l'import
    display_name = fields.Char(string='Nom', compute='_compute_display_name', store=True)
    name = fields.Char(string='Nom', related='display_name', store=True)
    import_date = fields.Datetime(string='Date d\'import', default=fields.Datetime.now, required=True)
    file_name = fields.Char(string='Nom du fichier')
    import_type = fields.Selection([
        ('file', 'XLS'),
        ('manual', 'Saisie manuelle')
    ], string='Type d\'import', default='file')

    # Informations sur l'import
    total_reservations = fields.Integer(string='Total réservations', compute='_compute_stats', store=True)
    new_reservations = fields.Integer(string='Nouvelles réservations', compute='_compute_stats', store=True)
    duplicate_reservations = fields.Integer(string='Doublons évités', compute='_compute_stats', store=True)

    # Période couverte par l'import
    date_from = fields.Date(string='Date début', compute='_compute_period', store=True)
    date_to = fields.Date(string='Date fin', compute='_compute_period', store=True)

    # Propriétés concernées
    property_type_ids = fields.Many2many(
        'product.template',
        string='Types d\'hébergement',
        compute='_compute_properties',
        store=True
    )

    # Lignes d'import (réservations)
    line_ids = fields.One2many('booking.import.line', 'import_id', string='Réservations')

    # Données du fichier
    file_data = fields.Binary(string='Fichier')

    # Société
    company_id = fields.Many2one('res.company', string='Société',
                                 default=lambda self: self.env.company, required=True)

    # État de l'import
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('imported', 'Importé'),
        ('processed', 'Traité')
    ], string='État', default='draft')

    # Origine de l'import
    origin = fields.Selection([
        ('booking.com', 'Booking.com'),
        ('other', 'Autre'),
    ], string='Origine', default='booking.com')

    booking_com_reservations = fields.Integer(
        string='Réservations Booking.com',
        compute='_compute_origin_stats',
        store=False
    )
    other_reservations = fields.Integer(
        string='Autres réservations',
        compute='_compute_origin_stats',
        store=False
    )

    @api.depends('import_date', 'file_name', 'import_type')
    def _compute_display_name(self):
        for record in self:
            if record.import_type == 'manual':
                date_str = record.import_date.strftime('%d/%m/%Y %H:%M') if record.import_date else ''
                record.display_name = f"Saisie manuelle {date_str}"
            else:
                if record.file_name:
                    record.display_name = f"Import {record.file_name}"
                else:
                    date_str = record.import_date.strftime('%d/%m/%Y %H:%M') if record.import_date else ''
                    record.display_name = f"Import {date_str}"

    @api.depends('line_ids')
    def _compute_stats(self):
        for record in self:
            record.total_reservations = len(record.line_ids)
            # Pour calculer les nouvelles réservations et doublons,
            # il faudrait comparer avec les imports précédents
            record.new_reservations = len(record.line_ids)
            record.duplicate_reservations = 0

    @api.depends('line_ids.arrival_date')
    def _compute_period(self):
        for record in self:
            if record.line_ids:
                dates = record.line_ids.mapped('arrival_date')
                record.date_from = min(dates) if dates else False
                record.date_to = max(dates) if dates else False
            else:
                record.date_from = False
                record.date_to = False

    @api.depends('line_ids.property_type_id')
    def _compute_properties(self):
        for record in self:
            record.property_type_ids = record.line_ids.mapped('property_type_id')

    def action_import_excel_file(self):
        """Importe les réservations depuis un fichier Excel"""
        self.ensure_one()
        if not self.file_data:
            raise UserError("Aucun fichier XLS n'a été téléchargé.")

        try:
            # Lire le fichier Excel
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')

            # Filtrer les réservations confirmées
            df = df[df['Statut'].str.contains("ok", na=False)]
            df['Arrivée'] = pd.to_datetime(df['Arrivée'], errors='coerce')
            df['Départ'] = pd.to_datetime(df['Départ'], errors='coerce')

            # Créer/récupérer le partenaire Booking.com
            self._ensure_booking_partner()

            # Créer les lignes de réservation
            created_lines = []
            duplicates = 0

            for _, row in df.iterrows():
                line_data = self._prepare_line_data(row)

                # Vérifier si la réservation existe déjà
                if self._is_duplicate_reservation(line_data):
                    duplicates += 1
                    continue

                # Créer la ligne de réservation
                line = self.env['booking.import.line'].create(line_data)
                created_lines.append(line.id)

            self.duplicate_reservations = duplicates
            self.new_reservations = len(created_lines)
            self.state = 'imported'

            # Mettre à jour les déclarations trimestrielles
            self._update_quarter_declarations()

            _logger.info(f"Import terminé: {len(created_lines)} nouvelles réservations, {duplicates} doublons évités")

        except Exception as e:
            _logger.error(f"Erreur lors de l'importation: {e}")
            raise UserError(f"Erreur lors de l'importation: {str(e)}")

    def _ensure_booking_partner(self):
        """Assure que le partenaire Booking.com existe"""
        partner = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)
        if not partner:
            self.env['res.partner'].create({
                'name': 'Booking.com',
                'street': 'Herengracht 597',
                'city': 'Amsterdam',
                'zip': '1017 CE',
                'country_id': self.env['res.country'].search([('code', '=', 'NL')]).id,
                'phone': '+31 20 201 8800',
                'email': 'customer.service@booking.com',
                'is_company': True,
                'supplier_rank': 1,
            })

    def _prepare_line_data(self, row):
        """Prépare les données d'une ligne de réservation"""
        # Traiter le nom du client
        customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(row.get("Réservé par", ""))

        # Créer/récupérer le client
        partner = self._get_or_create_partner(row, customer_name)

        # Créer/récupérer le type d'hébergement
        property_type = self._get_or_create_property_type(row)

        # Traiter les montants financiers
        rate = self._clean_amount(row.get('Tarif', '0'))
        commission = self._clean_amount(row.get('Montant de la commission', '0'))

        return {
            'import_id': self.id,
            'partner_id': partner.id,
            'booker_id': partner.id,
            'property_type_id': property_type.id,
            'arrival_date': row.get('Arrivée'),
            'departure_date': row.get('Départ'),
            'reservation_date': row.get('Réservé le'),
            'duration_nights': row.get('Durée (nuits)', 0),
            'pax_nb': row.get('Personnes', 0),
            'children': count_integers_leq_12(str(row.get('Âges des enfants', ''))),
            'payment_status': row.get('Statut du paiement', ''),
            'status': row.get('Statut', 'ok'),
            'rate': rate,
            'commission_amount': commission,
            'booking_reference': row.get('Numéro de confirmation', ''),
        }

    def _get_or_create_partner(self, row, customer_name):
        """Récupère ou crée un partenaire client"""
        partner = self.env['res.partner'].search([('name', '=', customer_name)], limit=1)
        if not partner:
            booker_country = row.get('Booker country', '').strip()
            country_id = False
            if booker_country:
                country = self.env['res.country'].search([
                    ('code', '=', booker_country.upper())
                ], limit=1)
                country_id = country.id if country else False

            partner = self.env['res.partner'].create({
                'name': customer_name,
                'phone': row.get('Numéro de téléphone', ''),
                'country_id': country_id,
                'company_id': self.company_id.id
            })
        return partner

    def _get_or_create_property_type(self, row):
        """Récupère ou crée un type de propriété"""
        housing_type = row.get("Type d'hébergement", "")
        property_type = self.env['product.template'].search([('name', '=', housing_type)], limit=1)
        if not property_type:
            property_type = self.env['product.template'].create({
                'name': housing_type,
                'purchase_ok': False,
                'sale_ok': True,
                'type': 'service',
                'company_id': self.company_id.id
            })
        return property_type

    def _clean_amount(self, amount_str):
        """Nettoie et convertit un montant en float"""
        try:
            return float(str(amount_str).replace(' XPF', '').replace(',', '').strip() or 0)
        except (ValueError, AttributeError):
            return 0.0

    def _inverse_name_first_name(self, texte):
        """Inverse nom, prénom en prénom nom"""
        if ',' in texte:
            name, first_name = texte.split(',', 1)
            return first_name.strip() + ' ' + name.strip()
        return texte

    def _is_duplicate_reservation(self, line_data):
        """Vérifie si une réservation est un doublon"""
        existing = self.env['booking.import.line'].search([
            ('partner_id', '=', line_data['partner_id']),
            ('property_type_id', '=', line_data['property_type_id']),
            ('arrival_date', '=', line_data['arrival_date']),
            ('duration_nights', '=', line_data['duration_nights']),
            ('pax_nb', '=', line_data['pax_nb']),
        ], limit=1)
        return bool(existing)

    def _update_quarter_declarations(self):
        """Met à jour les déclarations trimestrielles concernées"""
        quarters_to_update = set()

        for line in self.line_ids:
            if line.arrival_date and line.property_type_id:
                year = line.arrival_date.year
                month = line.arrival_date.month
                quarters_to_update.add((line.property_type_id.id, year, month))

        for property_type_id, year, month in quarters_to_update:
            self.env['booking.quarter'].create_or_update_quarter(property_type_id, year, month)

    def action_process_import(self):
        """Traite l'import (génère les vues mensuelles et factures)"""
        self.ensure_one()

        # Créer ou mettre à jour les vues mensuelles
        self._create_monthly_views()

        self.state = 'processed'
        return True

    def _create_monthly_views(self):
        """Crée les vues mensuelles pour cet import"""
        months_to_create = set()

        for line in self.line_ids:
            if line.arrival_date and line.property_type_id:
                year = line.arrival_date.year
                month = line.arrival_date.month
                months_to_create.add((line.property_type_id, year, month))

        for property_type_id, year, month in months_to_create:
            self.env['booking.month'].create_or_update_month(property_type_id, year, month)

    def action_add_reservation(self):
        """Ouvre le wizard pour ajouter une réservation manuellement"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ajouter une réservation',
            'res_model': 'booking.import.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_import_id': self.id}
        }

    def action_view_quarters(self):
        """Affiche les déclarations trimestrielles liées"""
        quarters = set()
        for line in self.line_ids:
            if line.arrival_date and line.property_type_id:
                year = line.arrival_date.year
                month = line.arrival_date.month
                quarter = ((month - 1) // 3) + 1
                quarters.add((line.property_type_id.id, year, quarter))

        quarter_ids = []
        for property_type_id, year, quarter in quarters:
            quarter_record = self.env['booking.quarter'].search([
                ('property_type_id', '=', property_type_id),
                ('year', '=', year),
                ('quarter', '=', quarter)
            ])
            if quarter_record:
                quarter_ids.extend(quarter_record.ids)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Déclarations trimestrielles',
            'res_model': 'booking.quarter',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', quarter_ids)],
            'target': 'current',
        }

    def action_view_months(self):
        """Affiche les vues mensuelles liées"""
        months = set()
        for line in self.line_ids:
            if line.arrival_date and line.property_type_id:
                year = line.arrival_date.year
                month = line.arrival_date.month
                months.add((line.property_type_id.id, year, month))

        month_ids = []
        for property_type_id, year, month in months:
            month_record = self.env['booking.month'].search([
                ('property_type_id', '=', property_type_id),
                ('year', '=', year),
                ('month', '=', month)
            ])
            if month_record:
                month_ids.extend(month_record.ids)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Vues mensuelles',
            'res_model': 'booking.month',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', month_ids)],
            'target': 'current',
        }

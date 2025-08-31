# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import pandas as pd
import base64
import io
import logging
from datetime import datetime

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


class BookingImportWizard(models.TransientModel):
    _name = 'booking.import.wizard'
    _description = 'Assistant d\'importation de fichier Booking.com'

    file_data = fields.Binary(string='Fichier Excel', required=True)
    file_name = fields.Char(string='Nom du fichier')
    preview_data = fields.Text(string='Aperçu des données', readonly=True)
    state = fields.Selection([
        ('upload', 'Upload du fichier'),
        ('preview', 'Aperçu des données'),
        ('confirm', 'Confirmation')
    ], default='upload', string='Étape')

    # Champs pour l'aperçu et validation
    total_records = fields.Integer(string='Nombre total d\'enregistrements', readonly=True)
    valid_records = fields.Integer(string='Enregistrements valides', readonly=True)
    duplicate_records = fields.Integer(string='Doublons détectés', readonly=True)

    # Import créé
    import_id = fields.Many2one('booking.import', string='Import créé', readonly=True)

    def action_preview(self):
        """Prévisualise les données du fichier avant import"""
        self.ensure_one()

        if not self.file_data:
            raise UserError("Veuillez sélectionner un fichier à importer.")

        try:
            # Lire le fichier Excel
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')

            self.total_records = len(df)

            # Filtrer les enregistrements valides
            valid_df = df[df['Statut'].str.contains("ok", na=False)]
            self.valid_records = len(valid_df)

            # Détection des doublons potentiels
            duplicates = self._detect_duplicates(valid_df)
            self.duplicate_records = len(duplicates)

            # Créer un aperçu des données
            preview_lines = []
            preview_lines.append(f"📊 RÉSUMÉ:")
            preview_lines.append(f"  • Total enregistrements: {self.total_records}")
            preview_lines.append(f"  • Enregistrements valides: {self.valid_records}")
            preview_lines.append(f"  • Doublons potentiels: {self.duplicate_records}")
            preview_lines.append("")

            # Afficher les propriétés détectées
            properties = valid_df["Type d'hébergement"].unique()
            preview_lines.append(f"🏠 PROPRIÉTÉS DÉTECTÉES ({len(properties)}):")
            for prop in properties[:5]:  # Limiter à 5
                count = len(valid_df[valid_df["Type d'hébergement"] == prop])
                preview_lines.append(f"  • {prop}: {count} réservations")
            if len(properties) > 5:
                preview_lines.append(f"  • ... et {len(properties) - 5} autres")
            preview_lines.append("")

            # Période couverte
            valid_df['Arrivée'] = pd.to_datetime(valid_df['Arrivée'], errors='coerce')
            dates = valid_df['Arrivée'].dropna()
            if not dates.empty:
                date_min = dates.min().strftime('%d/%m/%Y')
                date_max = dates.max().strftime('%d/%m/%Y')
                preview_lines.append(f"📅 PÉRIODE: du {date_min} au {date_max}")
                preview_lines.append("")

            # Aperçu des premières réservations
            preview_lines.append("📋 APERÇU DES RÉSERVATIONS:")
            for idx, row in valid_df.head(8).iterrows():
                customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(
                    row.get("Réservé par", ""))
                housing_type = row.get("Type d'hébergement", "")
                arrival_date = row.get('Arrivée', "")
                if hasattr(arrival_date, 'strftime'):
                    arrival_date = arrival_date.strftime('%d/%m/%Y')
                duration = row.get('Durée (nuits)', 0)
                pax = row.get('Personnes', 0)

                preview_lines.append(f"  • {customer_name} - {housing_type}")
                preview_lines.append(f"    {arrival_date} ({duration} nuits, {pax} pers.)")

            if len(valid_df) > 8:
                preview_lines.append(f"  • ... et {len(valid_df) - 8} autres réservations")

            # Afficher les doublons si détectés
            if duplicates:
                preview_lines.append("")
                preview_lines.append("⚠️  DOUBLONS DÉTECTÉS:")
                for duplicate in duplicates[:3]:  # Limiter à 3
                    preview_lines.append(f"  • {duplicate}")
                if len(duplicates) > 3:
                    preview_lines.append(f"  • ... et {len(duplicates) - 3} autres")
                preview_lines.append("")
                preview_lines.append("Les doublons seront automatiquement évités lors de l'import.")

            self.preview_data = "\n".join(preview_lines)
            self.state = 'preview'

        except Exception as e:
            _logger.error(f"Erreur lors de la prévisualisation : {e}")
            raise UserError(f"Erreur lors de la lecture du fichier : {str(e)}")

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }

    def action_import(self):
        """Effectue l'importation des données"""
        self.ensure_one()

        if not self.file_data:
            raise UserError("Aucun fichier à importer.")

        try:
            # Créer l'enregistrement d'import
            import_record = self.env['booking.import'].create({
                'import_type': 'file',
                'file_name': self.file_name,
                'file_data': self.file_data,
                'import_date': fields.Datetime.now(),
                'company_id': self.env.company.id,
                'state': 'draft',
            })

            # Effectuer l'import
            import_record.import_excel_file()

            # Traiter l'import (créer les vues mensuelles)
            import_record.action_process_import()

            self.import_id = import_record.id
            self.state = 'confirm'

            return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'res_id': self.id,
                'target': 'new',
                'context': self.env.context,
            }

        except Exception as e:
            _logger.error(f"Erreur lors de l'importation : {e}")
            raise UserError(f"Erreur lors de l'importation : {str(e)}")

    def action_view_import(self):
        """Affiche l'import créé"""
        if self.import_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'booking.import',
                'view_mode': 'form',
                'res_id': self.import_id.id,
                'target': 'current',
            }
        return {'type': 'ir.actions.act_window_close'}

    def _detect_duplicates(self, df):
        """Détecte les doublons potentiels dans le DataFrame"""
        duplicates = []
        seen = set()

        for _, row in df.iterrows():
            # Créer une clé unique basée sur les critères de doublon
            customer_name = row.get('Nom du client', '') or self._inverse_name_first_name(row.get("Réservé par", ""))
            arrival_date = str(row.get('Arrivée', ''))
            duration = str(row.get('Durée (nuits)', ''))
            pax = str(row.get('Personnes', ''))
            property_type = row.get("Type d'hébergement", "")

            key = f"{customer_name}|{arrival_date}|{duration}|{pax}|{property_type}"

            if key in seen:
                duplicates.append(f"{customer_name} - {arrival_date} ({property_type})")
            else:
                seen.add(key)

        return duplicates

    def _inverse_name_first_name(self, texte):
        """Inverse nom, prénom en prénom nom"""
        if ',' in texte:
            name, first_name = texte.split(',', 1)
            return first_name.strip() + ' ' + name.strip()
        return texte

    def action_cancel(self):
        """Annule le wizard"""
        return {'type': 'ir.actions.act_window_close'}


class BookingManualWizard(models.TransientModel):
    _name = 'booking.manual.wizard'
    _description = 'Assistant de création d\'import manuel'

    year = fields.Integer(string='Année', required=True, default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('1', 'Janvier'), ('2', 'Février'), ('3', 'Mars'), ('4', 'Avril'),
        ('5', 'Mai'), ('6', 'Juin'), ('7', 'Juillet'), ('8', 'Août'),
        ('9', 'Septembre'), ('10', 'Octobre'), ('11', 'Novembre'), ('12', 'Décembre')
    ], string='Mois', required=True, default=lambda self: str(fields.Date.today().month))

    property_type_id = fields.Many2one(
        'product.template',
        string='Type d\'hébergement',
        domain="[('sale_ok', '=', True), ('purchase_ok', '=', False)]",
        help="Sélectionnez le type d'hébergement pour lequel créer l'import manuel"
    )

    import_name = fields.Char(
        string='Nom de l\'import',
        help="Laissez vide pour générer automatiquement"
    )

    # Import créé
    import_id = fields.Many2one('booking.import', string='Import créé', readonly=True)

    state = fields.Selection([
        ('upload', 'Upload du fichier'),
        ('preview', 'Aperçu des données'),
        ('confirm', 'Confirmation')
    ], default='upload', string='Étape')

    def action_create_import(self):
        """Crée un nouvel enregistrement d'import pour saisie manuelle"""
        self.ensure_one()

        # Générer le nom automatiquement si non fourni
        if not self.import_name:
            month_name = datetime(1900, self.month, 1).strftime('%B').capitalize()
            self.import_name = f"{month_name} {self.year} - {self.property_type_id.name}"

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

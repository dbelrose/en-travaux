from odoo import models, fields, api
from collections import defaultdict
from datetime import datetime
from odoo.exceptions import UserError

import pandas as pd
import logging
import base64
import io
import num2words
import re

_logger = logging.getLogger(__name__)

global import_record, year, month, property_type

taxe: int = 60  # taxe fixe en XPF


# Fonction pour compter les entiers inférieurs ou égaux à 12
def count_integers_leq_12(s):
    if not s or s == '':
        return 0

    numbers = s.split(', ')
    count = sum(1 for num in numbers
                if num.strip() and num.strip().isdigit()
                and int(num.strip()) <= 12)
    return count


# First day of next month
def first_day_of_next_month(date):
    year_part = date.year + (date.month // 12)
    month_part = (date.month % 12) + 1
    return datetime(year_part, month_part, 1)


class BookingImport(models.Model):
    _name = 'booking.import'
    _description = 'Importation des données Booking.com'

    date = fields.Char(string='Date', compute='_compute_date', store=False)

    @api.depends()
    def _compute_date(self):
        today_str = datetime.today().strftime('%d/%m/%Y')
        for rec in self:
            rec.date = today_str

    name = fields.Char(string='Nom', compute='_compute_name', store=True)
    import_date = fields.Datetime(string='Date d\'importation', default=fields.Datetime.now)
    file_data = fields.Binary(string='Fichier Excel')
    file_name = fields.Char(string='Nom du fichier')
    line_ids = fields.One2many('booking.import.line', 'import_id', string='Lignes importées')

    invoice_id = fields.Many2one('account.move', string='Facture')
    property_type_id = fields.Many2one('product.template', string='Logement', store=True)
    total_commission = fields.Float(string='Total Commission',  compute='_compute_total_commission')
    month = fields.Selection(
        selection=[(str(i), datetime(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mois',
        store=True,
    )
    year = fields.Integer(string='Année', store=True)

    nom = fields.Char(string='Nom imprimé', compute='_compute_nom', store=True)
    adresse = fields.Char(string='Adresse', compute='_compute_adresse', store=True)
    capacite = fields.Char(string='Capacité', compute='_compute_capacite', store=True)
    periode = fields.Char(string='Période', compute='_compute_period', store=True)

    plus_nuitees_mois1 = fields.Char(string='Nuitées Mois 1', compute='_compute_plus_nuitees_mois1', store=True)
    plus_nuitees_mois2 = fields.Char(string='Nuitées Mois 2', compute='_compute_plus_nuitees_mois2', store=True)
    plus_nuitees_mois3 = fields.Char(string='Nuitées Mois 3', compute='_compute_plus_nuitees_mois3', store=True)
    plus_nuitees_trimestre = fields.Char(string='Nuitées Trimestre', compute='_compute_plus_nuitees_trimestre',
                                         store=True)
    moins_nuitees_mois1 = fields.Char(string='Nuitées Exonérées Mois 1', compute='_compute_moins_nuitees_mois1',
                                      store=True)
    moins_nuitees_mois2 = fields.Char(string='Nuitées Exonérées Mois 2', compute='_compute_moins_nuitees_mois2',
                                      store=True)
    moins_nuitees_mois3 = fields.Char(string='Nuitées Exonérées Mois 3', compute='_compute_moins_nuitees_mois3',
                                      store=True)
    moins_nuitees_trimestre = fields.Char(string='Nuitées Exonérées Trimestre',
                                          compute='_compute_moins_nuitees_trimestre', store=True)
    nuitees_mois1 = fields.Char(string='Taxes Perçues Mois 1', compute='_compute_nuitees_mois1', store=True)
    nuitees_mois2 = fields.Char(string='Taxes Perçues Mois 2', compute='_compute_nuitees_mois2', store=True)
    nuitees_mois3 = fields.Char(string='Taxes Perçues Mois 3', compute='_compute_nuitees_mois3', store=True)
    nuitees_trimestre = fields.Char(string='Taxes Perçues Trimestre', compute='_compute_nuitees_trimestre',
                                    store=True)
    total_mois1 = fields.Char(string='Total Mois 1', compute='_compute_total_mois1', store=True)
    total_mois2 = fields.Char(string='Total Mois 2', compute='_compute_total_mois2', store=True)
    total_mois3 = fields.Char(string='Total Mois 3', compute='_compute_total_mois3', store=True)
    total = fields.Char(string='Total', compute='_compute_total', store=True)
    total_en_toutes_lettres = fields.Char(string='Total en Toutes Lettres',
                                          compute='_compute_total_en_toutes_lettres', store=True)
    company_id = fields.Many2one(
        'res.company', string='Company', change_default=True,
        default=lambda self: self.env.company,
        required=False)

    def _to_int(self, value):
        try:
            return int(value or 0)
        except ValueError:
            return 0

    @api.onchange('file_name')
    def _onchange_file_name(self):
        for rec in self:
            if rec.file_name:
                match = re.search(r'du (\d{4})-(\d{2})-\d{2}', rec.file_name)
                if match:
                    year, month = match.groups()
                    rec.year = int(year)
                    rec.month = str(int(month))

    @api.onchange('import_date')
    def _onchange_import_date(self):
        for rec in self:
            if rec.import_date and not rec.file_name:
                rec.year = rec.import_date.year
                rec.month = str(rec.import_date.month)

    @api.depends('nuitees_mois1')
    def _compute_total_mois1(self):
        for rec in self:
            nuit = rec._to_int(rec.nuitees_mois1)
            rec.total_mois1 = str(nuit * taxe)

    @api.depends('nuitees_mois2')
    def _compute_total_mois2(self):
        for rec in self:
            nuit = rec._to_int(rec.nuitees_mois2)
            rec.total_mois2 = str(nuit * taxe)

    @api.depends('nuitees_mois3')
    def _compute_total_mois3(self):
        for rec in self:
            nuit = rec._to_int(rec.nuitees_mois3)
            rec.total_mois3 = str(nuit * taxe)

    @api.depends('total_mois1', 'total_mois2', 'total_mois3')
    def _compute_total(self):
        for rec in self:
            m1 = rec._to_int(rec.total_mois1)
            m2 = rec._to_int(rec.total_mois2)
            m3 = rec._to_int(rec.total_mois3)
            rec.total = str(m1 + m2 + m3)

    @api.depends('total')
    def _compute_total_en_toutes_lettres(self):
        for rec in self:
            total = rec._to_int(rec.total)
            if total:
                rec.total_en_toutes_lettres = num2words.num2words(total, lang='fr').capitalize() + " francs"
            else:
                rec.total_en_toutes_lettres = ""

    @api.depends('plus_nuitees_mois1', 'moins_nuitees_mois1')
    def _compute_nuitees_mois1(self):
        for rec in self:
            plus = rec._to_int(rec.plus_nuitees_mois1)
            moins = rec._to_int(rec.moins_nuitees_mois1)
            rec.nuitees_mois1 = str(plus - moins)

    @api.depends('plus_nuitees_mois2', 'moins_nuitees_mois2')
    def _compute_nuitees_mois2(self):
        for rec in self:
            plus = rec._to_int(rec.plus_nuitees_mois2)
            moins = rec._to_int(rec.moins_nuitees_mois2)
            rec.nuitees_mois2 = str(plus - moins)

    @api.depends('plus_nuitees_mois3', 'moins_nuitees_mois3')
    def _compute_nuitees_mois3(self):
        for rec in self:
            plus = rec._to_int(rec.plus_nuitees_mois3)
            moins = rec._to_int(rec.moins_nuitees_mois3)
            rec.nuitees_mois3 = str(plus - moins)

    @api.depends('nuitees_mois1', 'nuitees_mois2', 'nuitees_mois3')
    def _compute_nuitees_trimestre(self):
        for rec in self:
            m1 = rec._to_int(rec.nuitees_mois1)
            m2 = rec._to_int(rec.nuitees_mois2)
            m3 = rec._to_int(rec.nuitees_mois3)
            rec.nuitees_trimestre = str(m1 + m2 + m3)

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.pax_nb')
    def _compute_plus_nuitees_mois1(self):
        for record in self:
            record.plus_nuitees_mois1 = record._get_nuitees_for_trimestre_month(index=0)

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.pax_nb')
    def _compute_plus_nuitees_mois2(self):
        for record in self:
            record.plus_nuitees_mois2 = record._get_nuitees_for_trimestre_month(index=1)

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.pax_nb')
    def _compute_plus_nuitees_mois3(self):
        for record in self:
            record.plus_nuitees_mois3 = record._get_nuitees_for_trimestre_month(index=2)

    @api.depends('line_ids.commission_amount')
    def _compute_total_commission(self):
        for record in self:
            record.total_commission = sum(
                line.commission_amount or 0.0 for line in record.line_ids
            )

    def _get_nuitees_for_trimestre_month(self, index=0):
        """
        Retourne un string comme "12 nuitées en février", pour le X-ième mois du trimestre.
        """
        date_de_reference = next(
            (line.arrival_date for line in self.line_ids if line.arrival_date), None
        )

        property_de_reference = next(
            (line.property_type_id for line in self.line_ids if line.property_type_id), None
        )

        if not date_de_reference:
            return "0 nuitée"

        annee = date_de_reference.year
        mois = date_de_reference.month
        trimestre = (mois - 1) // 3 + 1
        mois_du_trimestre = [(trimestre - 1) * 3 + i for i in range(1, 4)]

        mois_cible = mois_du_trimestre[index]
        nuitees = 0

        tous_les_records = self.env[self._name].search([])

        for rec in tous_les_records:
            for line in rec.line_ids:
                if line.arrival_date and line.duration_nights:
                    if line.arrival_date.year == annee \
                            and line.arrival_date.month == mois_cible \
                            and line.property_type_id == property_de_reference:
                        nuitees += line.duration_nights * line.pax_nb

        return f"{nuitees}"

    @api.depends('plus_nuitees_mois1', 'plus_nuitees_mois2', 'plus_nuitees_mois3')
    def _compute_plus_nuitees_trimestre(self):
        for record in self:
            try:
                mois1 = float(record.plus_nuitees_mois1 or 0)
            except ValueError:
                mois1 = 0

            try:
                mois2 = float(record.plus_nuitees_mois2 or 0)
            except ValueError:
                mois2 = 0

            try:
                mois3 = float(record.plus_nuitees_mois3 or 0)
            except ValueError:
                mois3 = 0

            total = mois1 + mois2 + mois3
            record.plus_nuitees_trimestre = str(int(total))

    @api.depends('moins_nuitees_mois1', 'moins_nuitees_mois2', 'moins_nuitees_mois3')
    def _compute_moins_nuitees_trimestre(self):
        for record in self:
            try:
                mois1 = float(record.moins_nuitees_mois1 or 0)
            except ValueError:
                mois1 = 0

            try:
                mois2 = float(record.moins_nuitees_mois2 or 0)
            except ValueError:
                mois2 = 0

            try:
                mois3 = float(record.moins_nuitees_mois3 or 0)
            except ValueError:
                mois3 = 0

            total = mois1 + mois2 + mois3
            record.moins_nuitees_trimestre = str(int(total))

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.children')
    def _compute_moins_nuitees_mois1(self):
        for record in self:
            record.moins_nuitees_mois1 = record._get_moins_nuitees_mois(index=0)

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.children')
    def _compute_moins_nuitees_mois2(self):
        for record in self:
            record.moins_nuitees_mois2 = record._get_moins_nuitees_mois(index=1)

    @api.depends('line_ids.arrival_date', 'line_ids.duration_nights', 'line_ids.children')
    def _compute_moins_nuitees_mois3(self):
        for record in self:
            record.moins_nuitees_mois3 = record._get_moins_nuitees_mois(index=2)

    def _get_moins_nuitees_mois(self, index=0):
        """
        Retourne un string comme "12 nuitées en février", pour le X-ième mois du trimestre.
        """
        date_de_reference = next(
            (line.arrival_date for line in self.line_ids if line.arrival_date), None
        )

        property_de_reference = next(
            (line.property_type_id for line in self.line_ids if line.property_type_id), None
        )

        if not date_de_reference or not property_de_reference:
            return "0 nuitée"

        annee = date_de_reference.year
        mois = date_de_reference.month
        trimestre = (mois - 1) // 3 + 1
        mois_du_trimestre = [(trimestre - 1) * 3 + i for i in range(1, 4)]

        mois_cible = mois_du_trimestre[index]
        nuitees = 0

        tous_les_records = self.env[self._name].search([])

        for rec in tous_les_records:
            for line in rec.line_ids:
                if line.arrival_date and line.duration_nights:
                    if line.arrival_date.year == annee \
                            and line.arrival_date.month == mois_cible \
                            and line.property_type_id == property_de_reference:
                        nuitees += line.duration_nights * line.children

        return f"{nuitees}"

    def _get_nom_trimestre(self, mois):
        mapping = {
            1: 'Premier',
            2: 'Premier',
            3: 'Premier',
            4: 'Deuxième',
            5: 'Deuxième',
            6: 'Deuxième',
            7: 'Troisième',
            8: 'Troisième',
            9: 'Troisième',
            10: 'Quatrième',
            11: 'Quatrième',
            12: 'Quatrième',
        }
        return mapping.get(mois, 'Inconnu')

    @api.depends('line_ids.property_type_id.product_variant_ids.product_template_attribute_value_ids')
    def _compute_adresse(self):
        for record in self:
            adresse = False
            for line in record.line_ids:
                property_type = line.property_type_id
                if not property_type:
                    continue
                for variant in property_type.product_variant_ids:
                    _logger.info(f"[Adresse] Variant ID {variant.id} pour property_type {property_type.name}")
                    for val in variant.product_template_attribute_value_ids:
                        _logger.info(f"[Adresse] Attribut: {val.attribute_id.name} = {val.name}")
                        if val.attribute_id.name == 'Adresse':
                            adresse = val.name
                            break
                    if adresse:
                        break
                if adresse:
                    break
            record.adresse = adresse or "Adresse non renseignée"

    @api.depends('line_ids.property_type_id.product_variant_ids.product_template_attribute_value_ids')
    def _compute_capacite(self):
        for record in self:
            capacite = False
            _logger.info(f"[Capacité] Traitement du record ID {record.id}")
            for line in record.line_ids:
                property_type = line.property_type_id
                if not property_type:
                    continue
                for variant in property_type.product_variant_ids:
                    _logger.info(f"[Capacité] Variant ID {variant.id} pour property_type {property_type.name}")
                    for val in variant.product_template_attribute_value_ids:
                        _logger.info(f"[Capacité] Attribut: {val.attribute_id.name} = {val.name}")
                        if val.attribute_id.name == 'Capacité':
                            capacite = val.name
                            break
                    if capacite:
                        break
                if capacite:
                    break
            record.capacite = capacite or "Capacité non renseignée"

    @api.depends('line_ids.property_type_id.company_id.name')
    def _compute_nom(self):
        for record in self:
            nom = record.line_ids[0].property_type_id.company_id.name if record.line_ids else False
            record.nom = nom or "Nom non renseigné"

    @api.depends('line_ids.arrival_date')
    def _compute_period(self):
        for record in self:
            periode = False
            for line in record.line_ids:
                if line.arrival_date:
                    mois = line.arrival_date.month
                    annee = line.arrival_date.year
                    nom_trimestre = self._get_nom_trimestre(mois)
                    periode = f"{nom_trimestre} trimestre {annee}"
                    break  # On prend la première date trouvée
            record.periode = periode or "Trimestre inconnu"

    @api.depends('month', 'year', 'property_type_id')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.year}-{int(record.month):02d} {record.property_type_id.name}"

    def _inverse_name_first_name(self, texte):
        if ',' in texte:
            name, first_name = texte.split(',', 1)
            return first_name.strip() + ' ' + name.strip()
        return texte  # si la virgule est absente, on retourne tel quel

    def import_data(self):
        """ Fonction pour importer les données depuis un fichier Excel et créer tout en une seule opération. """
        global import_record, year, month, property_type

        self.ensure_one()
        if not self.file_data:
            _logger.warning("Aucun fichier n'a été téléchargé.")
            return

        try:
            # Lire le fichier Excel
            file_content = base64.b64decode(self.file_data)
            df = pd.read_excel(io.BytesIO(file_content))
            df.columns = df.columns.str.replace('&nbsp;', '')
            df = df.fillna('')  # Remplace tous les NaN par des chaînes vides
            df = df[df['Statut'].str.contains("ok", na=False)]  # Filtrage

            df['Arrivée'] = pd.to_datetime(df['Arrivée'], errors='coerce')

            # Vérifier si le partenaire Booking.com existe déjà
            supplier_id = self.env['res.partner'].search([('name', '=', 'Booking.com')], limit=1)
            if not supplier_id:
                supplier_id = self.env['res.partner'].create({
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

            # Vérifier ou créer le compte fournisseur
            account_id = self.env['account.account'].search([('code', '=', '411001')], limit=1)
            if not account_id:
                account_id = self.env['account.account'].create({
                    'name': 'Booking.com Payable',
                    'code': '411001',
                    'account_type': 'liability_payable',
                    'reconcile': True,
                })

            # Récupérer le journal de banque
            journal_id = self.env.ref('account.1_bank')

            # Récupérer la méthode de paiement
            payment_method_line = self.env['account.payment.method.line'].search([
                ('code', '=', 'manual'),
                ('payment_type', '=', 'inbound'),
                ('journal_id', '=', journal_id.id)
            ], limit=1)

            # Stocker les lignes d'importation dans une liste temporaire
            import_lines_data = []
            payment_vals_data = []
            total_commission = 0

            for _, row in df.iterrows():
                customer_name = row['Nom du client'] or self._inverse_name_first_name(row["Réservé par"])
                housing_type = row["Type d'hébergement"]
                phone_number = row['Numéro de téléphone']
                booker_country = row['Booker country']

                _logger.info(f"Client={customer_name}, Hébergement={housing_type}, Pays={booker_country}")

                # Rechercher ou créer le client
                partner = self.env['res.partner'].search([('name', '=', customer_name)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': customer_name,
                        'phone': phone_number,
                        'country_id': self.env['res.country'].search([('name', '=', booker_country)],
                                                                     limit=1).id,
                        'company_id': self.env.user.company_id.id
                    })

                # Rechercher ou créer le type d'hébergement
                property_type = self.env['product.template'].search([('name', '=', row["Type d'hébergement"])], limit=1)
                if not property_type:
                    property_type = self.env['product.template'].create({
                        'name': row["Type d'hébergement"],
                        'purchase_ok': False,
                        'company_id': self.env.user.company_id.id
                    })

                # Extraire l'année et le mois
                arrival_date = row['Arrivée'].strftime('%Y-%m-%d') if isinstance(row['Arrivée'], pd.Timestamp) else row[
                    'Arrivée']
                year, month = int(arrival_date[:4]), int(arrival_date[5:7])

                # Stocker les données pour booking.import.line
                import_lines_data.append((0, 0, {
                    'partner_id': partner.id,
                    'booker_id': partner.id,
                    'arrival_date': row['Arrivée'],
                    'duration_nights': row['Durée (nuits)'],
                    'children': count_integers_leq_12(str(row['Âges des enfants'])),
                    'property_type_id': property_type.id,
                    'payment_status': row['Statut du paiement'],
                    'status': row['Statut'],
                    'pax_nb': row['Personnes'],
                }))

                # Calcul de la commission totale
                total_commission += round(
                    float(row['Montant de la commission'].replace(' XPF', '').replace(',', '').strip()))

            # Regrouper les lignes par (year, month, property_type_id)
            grouped_lines = defaultdict(list)

            for _, row in df.iterrows():
                customer_name = row['Nom du client'] or self._inverse_name_first_name(row["Réservé par"])

                arrival_date = pd.to_datetime(row['Arrivée'], errors='coerce')
                if pd.isnull(arrival_date):
                    continue

                year = arrival_date.year
                month = arrival_date.month

                # Rechercher ou créer le client
                partner = self.env['res.partner'].search([('name', '=', customer_name)], limit=1)
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': customer_name,
                        'phone': row['Numéro de téléphone'],
                        'country_id': self.env['res.country'].search([('name', '=', row['Booker country'])],
                                                                     limit=1).id,
                        'company_id': self.env.user.company_id.id
                    })

                # Rechercher ou créer le type d'hébergement
                property_type = self.env['product.template'].search([('name', '=', row["Type d'hébergement"])], limit=1)
                if not property_type:
                    property_type = self.env['product.template'].create({
                        'name': row["Type d'hébergement"],
                        'purchase_ok': False,
                        'company_id': self.env.user.company_id.id
                    })

                # Ajouter la ligne à la clé de regroupement
                key = (year, month, property_type.id)
                grouped_lines[key].append((0, 0, {
                    'partner_id': partner.id,
                    'booker_id': partner.id,
                    'arrival_date': arrival_date,
                    'duration_nights': row['Durée (nuits)'],
                    'children': count_integers_leq_12(str(row['Âges des enfants'])),
                    'property_type_id': property_type.id,
                    'payment_status': row['Statut du paiement'],
                    'status': row['Statut'],
                    'pax_nb': row['Personnes'],
                    'rate': float(row['Tarif'].replace(' XPF', '')),
                    'commission_amount': float(row['Montant de la commission']
                                               .replace(' XPF', '').replace(',', '').strip()),
                }))

            # Création des enregistrements maîtres par groupe
            created_imports = []
            for (year, month, property_type_id), lines in grouped_lines.items():
                property_type = self.env['product.template'].browse(property_type_id)
                import_record = self.search([
                    ('year', '=', year),
                    ('month', '=', str(month)),
                    ('property_type_id', '=', property_type_id)
                ], limit=1)

                if not import_record:
                    import_record = self.create({
                        'year': year,
                        'month': str(month),
                        'property_type_id': property_type_id,
                        'import_date': fields.Datetime.now(),
                        'company_id': self.env.company,
                        'line_ids': lines
                    })
                else:
                    import_record.write({'line_ids': lines})

                created_imports.append(import_record)

            self.env['account.payment'].create(payment_vals_data)

        except Exception as e:
            _logger.error(f"Erreur lors de l'importation des données : {e}")

        # Supprimer tous les enregistrements où name=0-00
        invalid_records = self.search([('name', '=', '0-00 False')])
        if invalid_records:
            invalid_records.unlink()

        self.municipality_invoice()
        self.concierge_invoice()
        self.booking_invoice()
        self.action_view_import_record()

    def action_view_import_record(self, import_record=None):
        if not import_record:
            import_record = self.env['booking.import'].search(
                [('company_id', '=', self.env.user.company_id.id)],
                order='id desc',
                limit=1
            )
        if import_record:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Détail de l\'importation',
                'res_model': 'booking.import',
                'view_mode': 'form',
                'res_id': import_record.id,
                'target': 'current',
            }
        else:
            # Optionnel : message d’erreur si aucun enregistrement trouvé
            raise UserError("Aucun enregistrement d'importation trouvé pour votre société.")

    def municipality_invoice(self):
        municipality = self.env['res.partner'].search([('name', '=', 'Mairie de Punaauia')], limit=1)
        if not municipality:
            raise ValueError("Le fournisseur 'Mairie de Punaauia' n'existe pas !")

        account_id = self.env['account.account'].search([('code', '=', '63513000'),
                                                         ('company_id', '=', self.env.user.company_id.id)], limit=1).id
        if not account_id:
            raise ValueError("Le compte comptable '63513000' n'existe pas !")

        bookings = self.env['booking.import'].search([])

        invoices_by_ref = {}

        for booking in bookings:
            trimestre = ((int(booking.month) - 1) // 3) + 1
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
                        mois_key = f"- Mois {i}"
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

    def concierge_invoice(self):
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

    def booking_invoice(self):
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

from odoo import models, fields, api
import logging
import num2words

_logger = logging.getLogger(__name__)


class BookingQuarter(models.Model):
    _name = 'booking.quarter'
    _description = 'Déclaration trimestrielle de taxe de séjour'
    _order = 'year desc, quarter desc, property_type_id'
    _rec_name = 'display_name'

    # Identification de la déclaration
    year = fields.Integer(string='Année', required=True)
    quarter = fields.Selection([
        ('1', 'Premier trimestre'),
        ('2', 'Deuxième trimestre'),
        ('3', 'Troisième trimestre'),
        ('4', 'Quatrième trimestre')
    ], string='Trimestre', required=True)
    property_type_id = fields.Many2one('product.template', string='Type d\'hébergement', required=True)
    company_id = fields.Many2one('res.company', string='Société', required=True,
                                 default=lambda self: self.env.company)

    # Nom d'affichage calculé
    display_name = fields.Char(string='Nom', compute='_compute_display_name', store=True)

    # Informations de l'établissement (calculées depuis property_type_id)
    establishment_name = fields.Char(string='Nom établissement', compute='_compute_establishment_info', store=True)
    establishment_address = fields.Char(string='Adresse', compute='_compute_establishment_info', store=True)
    establishment_capacity = fields.Char(string='Capacité', compute='_compute_establishment_info', store=True)

    # Nuitées par mois du trimestre (calculées depuis les réservations)
    nights_month1 = fields.Integer(string='Nuitées mois 1', compute='_compute_nights_data', store=True)
    nights_month2 = fields.Integer(string='Nuitées mois 2', compute='_compute_nights_data', store=True)
    nights_month3 = fields.Integer(string='Nuitées mois 3', compute='_compute_nights_data', store=True)
    total_nights = fields.Integer(string='Total nuitées', compute='_compute_nights_data', store=True)

    # Nuitées exonérées (enfants ≤ 12 ans)
    exempt_nights_month1 = fields.Integer(string='Nuitées exonérées mois 1', compute='_compute_nights_data', store=True)
    exempt_nights_month2 = fields.Integer(string='Nuitées exonérées mois 2', compute='_compute_nights_data', store=True)
    exempt_nights_month3 = fields.Integer(string='Nuitées exonérées mois 3', compute='_compute_nights_data', store=True)
    total_exempt_nights = fields.Integer(string='Total nuitées exonérées', compute='_compute_nights_data', store=True)

    # Nuitées taxables
    taxable_nights_month1 = fields.Integer(string='Nuitées taxables mois 1', compute='_compute_nights_data', store=True)
    taxable_nights_month2 = fields.Integer(string='Nuitées taxables mois 2', compute='_compute_nights_data', store=True)
    taxable_nights_month3 = fields.Integer(string='Nuitées taxables mois 3', compute='_compute_nights_data', store=True)
    total_taxable_nights = fields.Integer(string='Total nuitées taxables', compute='_compute_nights_data', store=True)

    # Produit et prix de la taxe de séjour
    tourist_tax_product_id = fields.Many2one('product.product', string='Produit taxe de séjour',
                                             compute='_compute_tax_product', store=True)
    tourist_tax_unit_price = fields.Float(string='Prix unitaire taxe', compute='_compute_tax_product', store=True)

    # Montants des taxes
    tax_amount_month1 = fields.Float(string='Montant taxe mois 1', compute='_compute_tax_amounts', store=True)
    tax_amount_month2 = fields.Float(string='Montant taxe mois 2', compute='_compute_tax_amounts', store=True)
    tax_amount_month3 = fields.Float(string='Montant taxe mois 3', compute='_compute_tax_amounts', store=True)
    total_tax_amount = fields.Float(string='Total taxes à payer', compute='_compute_tax_amounts', store=True)
    total_tax_words = fields.Char(string='Total en lettres', compute='_compute_tax_words', store=True)

    # Statut de la déclaration
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('declared', 'Déclaré')
    ], string='Statut', default='draft')

    # Référence vers la facture de taxe de séjour
    tax_invoice_id = fields.Many2one('account.move', string='Facture taxe de séjour')

    # Contrainte d'unicité
    _sql_constraints = [
        ('unique_quarter_property',
         'unique(year, quarter, property_type_id, company_id)',
         'Une seule déclaration par trimestre et par type d\'hébergement!')
    ]

    @api.depends('year', 'quarter', 'property_type_id')
    def _compute_display_name(self):
        for record in self:
            quarter_names = {1: '1er', 2: '2ème', 3: '3ème', 4: '4ème'}
            property_name = record.property_type_id.name if record.property_type_id else 'Sans propriété'
            record.display_name = f"{quarter_names.get(int(record.quarter) if record.quarter else 0, '')} T{record.quarter} {record.year} - {property_name}"

    @api.depends('property_type_id')
    def _compute_establishment_info(self):
        for record in self:
            if not record.property_type_id:
                record.establishment_name = ""
                record.establishment_address = ""
                record.establishment_capacity = ""
                continue

            # Récupérer les informations depuis les variants du produit
            establishment_name = ""
            establishment_address = ""
            establishment_capacity = ""

            for variant in record.property_type_id.product_variant_ids:
                for attr_value in variant.product_template_attribute_value_ids:
                    if attr_value.attribute_id.name == 'Nom':
                        establishment_name = attr_value.name
                    elif attr_value.attribute_id.name == 'Adresse':
                        establishment_address = attr_value.name
                    elif attr_value.attribute_id.name == 'Capacité':
                        establishment_capacity = attr_value.name

            # Fallback sur le nom de la société
            if not establishment_name and record.property_type_id.company_id:
                establishment_name = record.property_type_id.company_id.name

            record.establishment_name = establishment_name or "Non renseigné"
            record.establishment_address = establishment_address or "Non renseignée"
            record.establishment_capacity = establishment_capacity or "Non renseignée"

    @api.depends('company_id')
    def _compute_tax_product(self):
        """Récupère le produit et le prix de la taxe de séjour"""
        for record in self:
            # Rechercher le produit "Taxe de séjour"
            tax_product = self.env['product.product'].search([
                ('default_code', '=', 'TAXE_SEJOUR'),
                '|', ('company_id', '=', record.company_id.id), ('company_id', '=', False)
            ], limit=1)

            if not tax_product:
                # Fallback : recherche par nom
                tax_product = self.env['product.product'].search([
                    ('name', 'ilike', 'taxe de séjour'),
                    '|', ('company_id', '=', record.company_id.id), ('company_id', '=', False)
                ], limit=1)

            if tax_product:
                record.tourist_tax_product_id = tax_product
                # Récupérer le prix depuis la liste de prix de la municipalité
                municipality = self._get_municipality_partner()
                if municipality and municipality.property_product_pricelist:
                    record.tourist_tax_unit_price = tax_product._get_price_in_pricelist(
                        municipality.property_product_pricelist
                    )
                else:
                    record.tourist_tax_unit_price = tax_product.list_price
            else:
                record.tourist_tax_product_id = False
                record.tourist_tax_unit_price = 60.0  # Valeur par défaut
                _logger.warning("Produit 'Taxe de séjour' introuvable, utilisation du prix par défaut (60 XPF)")

    def _get_municipality_partner(self):
        """Récupère le partenaire municipalité"""
        return self.env['res.partner'].search([
            ('name', '=', 'Mairie de Punaauia')
        ], limit=1)

    @api.depends('year', 'quarter', 'property_type_id')
    def _compute_nights_data(self):
        """Calcule les nuitées depuis les réservations importées"""
        for record in self:
            if not record.year or not record.quarter or not record.property_type_id:
                record._reset_nights_data()
                continue

            # Calculer les mois du trimestre
            start_month = (int(record.quarter) - 1) * 3 + 1
            months = [start_month, start_month + 1, start_month + 2]

            # Rechercher toutes les réservations pour ce type de propriété et cette période
            reservations = self.env['booking.import.line'].search([
                ('property_type_id', '=', record.property_type_id.id),
                ('arrival_date', '>=', f"{record.year}-{months[0]:02d}-01"),
                ('arrival_date', '<', f"{record.year + (1 if months[2] > 12 else 0)}-{(months[2] % 12) + 1:02d}-01"),
                ('status', '=', 'ok')  # Seules les réservations confirmées
            ])

            # Initialiser les compteurs
            nights_data = {
                'nights_month1': 0, 'nights_month2': 0, 'nights_month3': 0,
                'exempt_nights_month1': 0, 'exempt_nights_month2': 0, 'exempt_nights_month3': 0
            }

            for reservation in reservations:
                month_index = reservation.arrival_date.month - start_month
                if 0 <= month_index <= 2:
                    month_key = f'month{month_index + 1}'

                    # Calculer nuitées adultes et enfants
                    adult_nights = reservation.nights_adults
                    child_nights = reservation.nights_children

                    nights_data[f'nights_{month_key}'] += adult_nights
                    nights_data[f'exempt_nights_{month_key}'] += child_nights

            # Mettre à jour les champs
            record.nights_month1 = nights_data['nights_month1']
            record.nights_month2 = nights_data['nights_month2']
            record.nights_month3 = nights_data['nights_month3']
            record.total_nights = sum([nights_data[f'nights_month{i}'] for i in range(1, 4)])

            record.exempt_nights_month1 = nights_data['exempt_nights_month1']
            record.exempt_nights_month2 = nights_data['exempt_nights_month2']
            record.exempt_nights_month3 = nights_data['exempt_nights_month3']
            record.total_exempt_nights = sum([nights_data[f'exempt_nights_month{i}'] for i in range(1, 4)])

            record.taxable_nights_month1 = record.nights_month1
            record.taxable_nights_month2 = record.nights_month2
            record.taxable_nights_month3 = record.nights_month3
            record.total_taxable_nights = record.total_nights

    def _reset_nights_data(self):
        """Remet à zéro les données de nuitées"""
        self.nights_month1 = 0
        self.nights_month2 = 0
        self.nights_month3 = 0
        self.total_nights = 0
        self.exempt_nights_month1 = 0
        self.exempt_nights_month2 = 0
        self.exempt_nights_month3 = 0
        self.total_exempt_nights = 0
        self.taxable_nights_month1 = 0
        self.taxable_nights_month2 = 0
        self.taxable_nights_month3 = 0
        self.total_taxable_nights = 0

    @api.depends('taxable_nights_month1', 'taxable_nights_month2', 'taxable_nights_month3', 'tourist_tax_unit_price')
    def _compute_tax_amounts(self):
        for record in self:
            unit_price = record.tourist_tax_unit_price
            record.tax_amount_month1 = record.taxable_nights_month1 * unit_price
            record.tax_amount_month2 = record.taxable_nights_month2 * unit_price
            record.tax_amount_month3 = record.taxable_nights_month3 * unit_price
            record.total_tax_amount = record.tax_amount_month1 + record.tax_amount_month2 + record.tax_amount_month3

    @api.depends('total_tax_amount')
    def _compute_tax_words(self):
        for record in self:
            if record.total_tax_amount:
                record.total_tax_words = num2words.num2words(int(record.total_tax_amount),
                                                             lang='fr').capitalize() + " francs CFP"
            else:
                record.total_tax_words = ""

    def action_recalculate(self):
        """Force le recalcul des données"""
        self._compute_nights_data()
        self._compute_tax_product()
        return True

    def action_confirm(self):
        """Confirme la déclaration"""
        self.state = 'confirmed'

    def action_declare(self):
        """Marque la déclaration comme déclarée"""
        self.state = 'declared'

    def action_generate_tax_invoice(self):
        """Génère la facture de taxe de séjour vers la mairie - Version avec produits paramétrables"""
        self.ensure_one()

        # Rechercher le partenaire mairie
        municipality = self._get_municipality_partner()
        if not municipality:
            raise ValueError("Le partenaire 'Mairie de Punaauia' n'existe pas!")

        # S'assurer que le partenaire est configuré comme fournisseur
        if not municipality.is_company:
            municipality.write({'is_company': True})
        if not municipality.supplier_rank:
            municipality.write({'supplier_rank': 1})

        # Vérifier le produit taxe de séjour
        if not self.tourist_tax_product_id:
            raise ValueError(
                "Produit 'Taxe de séjour' introuvable! Veuillez créer un produit avec le code 'TAXE_SEJOUR'.")

        # Compte comptable depuis le produit
        account_id = self.tourist_tax_product_id.product_tmpl_id._get_product_accounts()['expense']
        if not account_id:
            # Compte par défaut
            account_id = self.env['account.account'].search([
                ('code', '=', '63513000'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            if not account_id:
                raise ValueError("Aucun compte comptable configuré pour la taxe de séjour!")

        # Journal de factures fournisseur
        journal = self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not journal:
            raise ValueError("Aucun journal de type 'purchase' trouvé!")

        # Dates
        today = fields.Date.context_today(self)
        invoice_date = today
        invoice_date_due = fields.Date.add(today, days=30)

        # Préparer les lignes de facture
        invoice_lines = []
        month_names = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                       'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

        start_month = (int(self.quarter) - 1) * 3 + 1

        for i in range(3):
            month_num = start_month + i
            month_name = month_names[month_num]
            taxable_nights = getattr(self, f'taxable_nights_month{i + 1}')

            if taxable_nights > 0:
                line_vals = (0, 0, {
                    'product_id': self.tourist_tax_product_id.id,
                    'name': f"Taxe de séjour {month_name} {self.year} - {self.property_type_id.name} ({taxable_nights} nuitées)",
                    'quantity': taxable_nights,
                    'price_unit': self.tourist_tax_unit_price,
                    'account_id': account_id.id,
                    'tax_ids': [(6, 0, [])],  # Pas de taxes
                })
                invoice_lines.append(line_vals)

        if not invoice_lines:
            raise ValueError("Aucune nuitée taxable trouvée pour ce trimestre!")

        # Supprimer l'ancienne facture si elle existe
        if self.tax_invoice_id:
            old_invoice = self.tax_invoice_id
            try:
                if old_invoice.state == 'posted':
                    old_invoice.button_draft()
                old_invoice.unlink()
            except Exception:
                pass  # Ignorer les erreurs de suppression
            self.tax_invoice_id = False

        # Créer la nouvelle facture
        try:
            payment_term_30 = self.env.ref('account.account_payment_term_30days', raise_if_not_found=False)
            if not payment_term_30:
                payment_term_30 = self.env['account.payment.term'].search([
                    ('name', 'ilike', '30')
                ], limit=1)

            invoice_vals = {
                'partner_id': municipality.id,
                'move_type': 'in_invoice',
                'invoice_date': invoice_date,
                'ref': f"Taxe séjour T{self.quarter} {self.year} - {self.property_type_id.name}",
                'narration': f"Déclaration trimestrielle de taxe de séjour - Trimestre {self.quarter} {self.year}",
                'company_id': self.company_id.id,
                'journal_id': journal.id,
                'currency_id': self.company_id.currency_id.id,
                'invoice_line_ids': invoice_lines,
                'invoice_incoterm_id': False,
                'fiscal_position_id': False,
                'invoice_payment_term_id': payment_term_30.id if payment_term_30 else False,
            }

            # Créer avec contexte spécifique
            invoice = self.env['account.move'].with_context(
                default_move_type='in_invoice',
                move_type='in_invoice',
                journal_type='purchase',
                default_journal_id=journal.id
            ).create(invoice_vals)

            self.tax_invoice_id = invoice

            # Forcer le recalcul des champs automatiques
            invoice._onchange_partner_id()

            # Valider la facture
            invoice.action_post()

        except Exception as e:
            # Log détaillé de l'erreur
            _logger.error(f"Erreur création facture taxe séjour: {str(e)}")
            _logger.error(f"Partenaire: {municipality.name} (ID: {municipality.id})")
            _logger.error(f"Journal: {journal.name} (ID: {journal.id})")
            _logger.error(f"Produit: {self.tourist_tax_product_id.name} (ID: {self.tourist_tax_product_id.id})")
            raise ValueError(f"Erreur lors de la création de la facture: {str(e)}")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
            'target': 'current',
        }

    @api.model
    def create_or_update_quarter(self, property_type_id, year, month):
        """Crée ou met à jour une déclaration trimestrielle"""
        quarter = str(((month - 1) // 3) + 1)

        quarter_record = self.search([
            ('year', '=', year),
            ('quarter', '=', quarter),
            ('property_type_id', '=', property_type_id),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not quarter_record:
            quarter_record = self.create({
                'year': year,
                'quarter': quarter,
                'property_type_id': property_type_id,
                'company_id': self.env.company.id,
            })
        else:
            # Forcer le recalcul
            quarter_record.action_recalculate()

        return quarter_record


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_price_in_pricelist(self, pricelist):
        """Récupère le prix du produit dans une liste de prix donnée"""
        if not pricelist:
            return self.list_price

        price = pricelist._get_product_price(self, 1.0)
        return price if price else self.list_price

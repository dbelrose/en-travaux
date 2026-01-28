# Extension du modèle booking.month pour ajouter la gestion des factures clients

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BookingMonth(models.Model):
    _inherit = 'booking.month'

    # Champs pour les factures clients
    customer_invoices_generated = fields.Boolean(
        string="Factures clients générées",
        default=False,
        help="Indique si les factures clients ont été générées pour ce mois"
    )

    customer_invoice_ids = fields.One2many(
        'account.move',
        'booking_month_id',
        string="Factures clients",
        domain=[('move_type', '=', 'out_invoice')]
    )

    total_customer_invoices = fields.Integer(
        string="Nombre factures clients",
        compute='_compute_customer_invoices_stats',
        store=True
    )

    customer_invoices_amount = fields.Monetary(
        string="Montant factures clients",
        compute='_compute_customer_invoices_stats',
        store=True,
        currency_field='company_currency_id'
    )

    # État de facturation mis à jour
    invoice_state = fields.Selection([
        ('none', 'Aucune facture'),
        ('booking_only', 'Booking.com seulement'),
        ('concierge_only', 'Concierge seulement'),
        ('customer_only', 'Clients seulement'),
        ('booking_concierge', 'Booking.com + Concierge'),
        ('booking_customer', 'Booking.com + Clients'),
        ('concierge_customer', 'Concierge + Clients'),
        ('all', 'Toutes les factures'),
    ], string='État facturation', compute='_compute_invoice_state', store=True)

    # 0 / 33 / 66 / 100 pour la barre de progression
    invoice_state_progress = fields.Integer(
        string='Facturation',
        compute='_compute_invoice_state_progress',
        store=True,
        readonly=True,
        help='Avancement facturation (%) : 0=Aucune facture, 33-66=Partiel, 100=Toutes les factures'
    )

    @api.depends('invoice_state')
    def _compute_invoice_state_progress(self):
        """Mappe invoice_state -> pourcentage.
           none -> 0, partial -> 50, complete -> 100.
        """
        mapping = {
            'none': 0,
            'booking_only': 33,
            'concierge_only': 33,
            'customer_only': 33,
            'booking_concierge': 66,
            'booking_customer': 66,
            'concierge_customer': 66,
            'all': 100,
        }
        for rec in self:
            rec.invoice_state_progress = mapping.get(rec.invoice_state or 'none', 0)

    @api.depends('customer_invoice_ids', 'customer_invoice_ids.amount_total')
    def _compute_customer_invoices_stats(self):
        for record in self:
            customer_invoices = record.customer_invoice_ids.filtered(
                lambda inv: inv.state != 'cancel'
            )
            record.total_customer_invoices = len(customer_invoices)
            record.customer_invoices_amount = sum(customer_invoices.mapped('amount_total'))

    @api.depends('booking_invoice_id', 'concierge_invoice_id', 'customer_invoice_ids')
    def _compute_invoice_state(self):
        for record in self:
            has_booking = bool(record.booking_invoice_id)
            has_concierge = bool(record.concierge_invoice_id)
            has_customer = bool(record.customer_invoice_ids)
            # has_customer = record.customer_invoices_generated

            if has_booking and has_concierge and has_customer:
                record.invoice_state = 'all'
            elif has_booking and has_concierge:
                record.invoice_state = 'booking_concierge'
            elif has_booking and has_customer:
                record.invoice_state = 'booking_customer'
            elif has_concierge and has_customer:
                record.invoice_state = 'concierge_customer'
            elif has_booking:
                record.invoice_state = 'booking_only'
            elif has_concierge:
                record.invoice_state = 'concierge_only'
            elif has_customer:
                record.invoice_state = 'customer_only'
            else:
                record.invoice_state = 'none'

    def action_generate_customer_invoices(self):
        """Génère les factures clients pour toutes les réservations du mois"""
        # Pas de ensure_one() - permet le traitement multiple

        invoices_created = 0
        errors = []

        for record in self:
            # Vérifier si déjà généré
            if record.customer_invoice_ids:
                continue  # Passer au suivant au lieu de lever une erreur

            record.customer_invoices_generated = False

            # Récupérer les réservations du mois
            reservations = record._get_month_reservations()

            if not reservations:
                continue  # Pas de réservations, passer au suivant

            # Récupérer la configuration
            config = self.env.context.get('customer_invoice_config', {})
            group_by_customer = config.get('group_by_customer', True)

            try:
                if group_by_customer:
                    # Grouper par client
                    customers = reservations.mapped('partner_id')

                    for customer in customers:
                        customer_reservations = reservations.filtered(lambda r: r.partner_id == customer)
                        invoice = record._create_customer_invoice(customer, customer_reservations)

                        if invoice:
                            invoices_created += 1
                else:
                    # Une facture par réservation
                    for reservation in reservations:
                        if reservation.partner_id:
                            invoice = record._create_customer_invoice(reservation.partner_id, [reservation])
                            if invoice:
                                invoices_created += 1

                # Marquer comme généré
                record.customer_invoices_generated = True

            except Exception as e:
                errors.append(f"{record.display_name}: {str(e)}")

        # Retourner une notification appropriée
        if errors:
            message = f"{invoices_created} facture(s) générée(s), {len(errors)} erreur(s)"
            notif_type = 'warning'
        else:
            message = f"{invoices_created} facture(s) client(s) générée(s)"
            notif_type = 'success'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Génération de factures clients',
                'message': message,
                'type': notif_type,
                'sticky': False,
            }
        }

    def _get_month_reservations(self):
        """Récupère les réservations du mois"""
        return self.env['booking.import.line'].search([
            ('property_type_id', '=', self.property_type_id.id),
            ('arrival_date', '>=', self.period_start),
            ('arrival_date', '<=', self.period_end),
            ('status', '=', 'ok'),  # Seulement les réservations confirmées
        ])

    def _create_customer_invoice(self, customer, reservations):
        """Crée une facture client avec 3 lignes par réservation"""

        # Récupérer les produits nécessaires
        accommodation_product = self._get_accommodation_product()
        tax_product = self._get_tax_product(accommodation_product)

        invoice_lines = []

        for reservation in reservations:
            # 1. Ligne hébergement (property_type)
            accommodation_line = self._create_accommodation_line(reservation, accommodation_product)
            invoice_lines.append((0, 0, accommodation_line))

            # 2. Ligne taxe de séjour
            # tax_line = self._create_tax_line(reservation, tax_product)
            # invoice_lines.append((0, 0, tax_line))

        # Créer la facture
        first_reservation = reservations[0] if reservations else None

        if first_reservation:
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': customer.id,
                'booking_month_id': self.id,
                'invoice_date_due': first_reservation.arrival_date or fields.Date.today(),
                'invoice_date': first_reservation.reservation_date or first_reservation.arrival_date or fields.Date.today(),
                'invoice_line_ids': invoice_lines,
            }

            invoice = self.env['account.move'].create(invoice_vals)

            return invoice

    def _create_accommodation_line(self, reservation, product):
        """Crée la ligne hébergement basée sur le property_type_id"""

        # Utiliser le tarif de la réservation moins la taxe
        net_rate = (reservation.rate - reservation.tax_amount or 0) / (reservation.nights_adults or 1)

        return {
            'product_id': product.id,
            'name': f"Hébergement {reservation.property_type_id.name} - {reservation.arrival_date.strftime('%d/%m/%Y')} ({reservation.duration_nights}n, {reservation.pax_nb}p)",
            'quantity': reservation.nights_adults,
            'price_unit': net_rate,
            'account_id': product.property_account_income_id.id or
                          product.categ_id.property_account_income_categ_id.id,
        }

    def _create_tax_line(self, reservation, product):
        """Crée la ligne taxe de séjour"""

        price_unit = reservation.tax_amount / reservation.nights_adults if reservation.nights_adults else 0.0

        return {
            'product_id': product.id,
            'name': f"Taxe de séjour - {reservation.nights_adults} nuitées adultes",
            'quantity': reservation.nights_adults,
            'price_unit': price_unit,  # 60 XPF par nuitée adulte
            'account_id': product.property_account_income_id.id or
                          product.categ_id.property_account_income_categ_id.id,
        }

    def _get_accommodation_product(self):
        """Récupère ou crée le produit hébergement"""

        product = self.property_type_id

        return product

    def _get_tax_product(self, accommodation_product):
        """Récupère ou crée le produit taxe de séjour"""

        product = self.env["product.template"].sudo().browse(accommodation_product.id)
        category = product.categ_id

        # Retourne un tuple (module, name) si l'xml_id existe
        xmlid = category.get_external_id().get(category.id)

        # Extraire uniquement le "name" de l'xml_id
        ref_interne = xmlid.split(".")[-1].replace("product_category_", "").upper()

        # Construire l'xml_id du produit taxe correspondant
        # xmlid_taxe = f"os_hospitality_managment.product_taxe_{ref_interne}"

        # Récupérer l'enregistrement du produit taxe
        # product_taxe = self.env.ref(xmlid_taxe, raise_if_not_found=False)
        product_taxe = self.env['product.product'].search([
            ('default_code', '=', ref_interne)
        ], limit=1)

        if product_taxe:
            product = product_taxe

        if not product:
            raise UserError(f"Le produit taxe de séjour pour la catégorie '{category.name}' n'existe pas. Veuillez le "
                            f"créer avant de générer les factures clients.")

        return product

    def action_view_customer_invoices(self):
        """Action pour voir les factures clients du mois"""
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': f'Factures clients - {self.display_name}',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.customer_invoice_ids.ids)],
            'context': {
                'default_move_type': 'out_invoice',
                'default_booking_month_id': self.id,
            }
        }

    def action_generate_all_invoices(self):
        """Génère toutes les factures (existante + nouvelles factures clients)"""

        # Appeler la méthode parente pour les factures existantes
        result = super().action_generate_all_invoices()

        # Ajouter la génération des factures clients si pas encore fait
        if not bool(self.customer_invoice_ids):
            try:
                self.action_generate_customer_invoices()
            except Exception as e:
                _logger.warning(f"Erreur lors de la génération des factures clients: {str(e)}")

        return result

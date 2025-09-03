# Extension du modèle booking.month pour ajouter la gestion des factures clients

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BookingMonth(models.Model):
    _inherit = 'booking.month'

    # Nouveaux champs pour les factures clients
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

    # Mise à jour du statut de facturation pour inclure les factures clients
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

    @api.depends('customer_invoice_ids', 'customer_invoice_ids.amount_total')
    def _compute_customer_invoices_stats(self):
        for record in self:
            customer_invoices = record.customer_invoice_ids.filtered(
                lambda inv: inv.state != 'cancel'
            )
            record.total_customer_invoices = len(customer_invoices)
            record.customer_invoices_amount = sum(customer_invoices.mapped('amount_total'))

    @api.depends('booking_invoice_id', 'concierge_invoice_id', 'customer_invoices_generated')
    def _compute_invoice_state(self):
        for record in self:
            has_booking = bool(record.booking_invoice_id)
            has_concierge = bool(record.concierge_invoice_id)
            has_customer = record.customer_invoices_generated

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
        _logger.info("=== DÉBUT action_generate_customer_invoices ===")

        self.ensure_one()
        _logger.info(f"Modèle: {self._name}, ID: {self.id}")

        if self.customer_invoices_generated:
            _logger.warning("Les factures clients ont déjà été générées pour ce mois.")
            raise UserError("Les factures clients ont déjà été générées pour ce mois.")

        _logger.info(f"Période: {self.period_start} à {self.period_end}")
        _logger.info(f"Type de propriété: {self.property_type_id.name if self.property_type_id else 'None'}")

        # Récupérer les réservations du mois
        domain = [
            ('property_type_id', '=', self.property_type_id.id),
            ('arrival_date', '>=', self.period_start),
            ('arrival_date', '<=', self.period_end),
            ('status', '=', 'ok'),  # Seulement les réservations confirmées
        ]
        _logger.info(f"Domaine de recherche: {domain}")

        reservations = self.env['booking.import.line'].search(domain)
        _logger.info(f"Nombre de réservations trouvées: {len(reservations)}")

        if reservations:
            for i, res in enumerate(reservations[:5]):  # Afficher les 5 premières
                _logger.info(
                    f"  Réservation {i + 1}: ID={res.id}, Client={res.partner_id.name if res.partner_id else 'Sans client'}, Date={res.arrival_date}")

        if not reservations:
            _logger.error("Aucune réservation trouvée pour ce mois.")
            raise UserError("Aucune réservation trouvée pour ce mois.")

        # Récupérer la configuration
        config = self.env.context.get('customer_invoice_config', {})
        _logger.info(f"Configuration du contexte: {config}")

        group_by_customer = config.get('group_by_customer', True)
        _logger.info(f"Grouper par client: {group_by_customer}")

        invoices_created = 0

        if group_by_customer:
            # Grouper par client pour éviter les factures multiples
            customers = reservations.mapped('partner_id')
            _logger.info(f"Nombre de clients uniques: {len(customers)}")

            if not customers:
                _logger.error("Aucun client trouvé dans les réservations")
                raise UserError("Aucun client trouvé dans les réservations")

            for i, customer in enumerate(customers):
                _logger.info(f"--- Traitement client {i + 1}/{len(customers)}: {customer.name} (ID: {customer.id}) ---")

                customer_reservations = reservations.filtered(lambda r: r.partner_id == customer)
                _logger.info(f"Réservations pour ce client: {len(customer_reservations)}")

                try:
                    _logger.info(f"Appel de _create_customer_invoice pour {customer.name}")
                    invoice = self._create_customer_invoice(customer, customer_reservations)
                    _logger.info(f"Retour de _create_customer_invoice: {invoice}")

                    if invoice:
                        invoices_created += 1
                        _logger.info(f"✓ Facture client créée: {invoice.name} pour {customer.name}")
                    else:
                        _logger.warning(f"✗ _create_customer_invoice a retourné None/False pour {customer.name}")

                except Exception as e:
                    _logger.error(f"✗ Erreur lors de la création de la facture pour {customer.name}: {str(e)}")
                    import traceback
                    _logger.error(f"Traceback: {traceback.format_exc()}")
                    continue
        else:
            # Créer une facture par réservation
            _logger.info("Mode: une facture par réservation")

            for i, reservation in enumerate(reservations):
                _logger.info(f"--- Traitement réservation {i + 1}/{len(reservations)}: ID={reservation.id} ---")

                if not reservation.partner_id:
                    _logger.warning(f"Réservation {reservation.id} sans client, ignorée")
                    continue

                try:
                    _logger.info(f"Appel de _create_customer_invoice pour réservation {reservation.id}")
                    invoice = self._create_customer_invoice(reservation.partner_id, [reservation])
                    _logger.info(f"Retour de _create_customer_invoice: {invoice}")

                    if invoice:
                        invoices_created += 1
                        _logger.info(f"✓ Facture client créée: {invoice.name} pour {reservation.partner_id.name}")
                    else:
                        _logger.warning(
                            f"✗ _create_customer_invoice a retourné None/False pour réservation {reservation.id}")

                except Exception as e:
                    _logger.error(
                        f"✗ Erreur lors de la création de la facture pour la réservation {reservation.id}: {str(e)}")
                    import traceback
                    _logger.error(f"Traceback: {traceback.format_exc()}")
                    continue

        _logger.info(
            f"RÉSUMÉ: {invoices_created} factures créées sur {len(customers) if group_by_customer else len(reservations)} tentatives")

        # Marquer comme généré
        self.customer_invoices_generated = True
        _logger.info("Marqué comme généré: customer_invoices_generated = True")

        message = f'{invoices_created} facture(s) client(s) générée(s)'
        _logger.info(f"Message de retour: {message}")
        _logger.info("=== FIN action_generate_customer_invoices ===")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': 'success'
            }
        }

    def _create_customer_invoice(self, customer, reservations):
        """Crée une facture client pour un groupe de réservations"""

        _logger.info("=== DÉBUT _create_customer_invoice ===")
        _logger.info(f"Customer: {customer.name if customer else 'None'}")
        _logger.info(f"Nombre de réservations: {len(reservations) if reservations else 0}")

        # Récupérer la configuration depuis le contexte ou utiliser les valeurs par défaut
        config = self.env.context.get('customer_invoice_config', {})
        _logger.info(f"Configuration: {config}")

        # Récupérer les produits selon la configuration
        accommodation_product = None
        if config.get('accommodation_product_id'):
            accommodation_product = self.env['product.product'].browse(config['accommodation_product_id'])
            _logger.info(f"Produit hébergement depuis config: {accommodation_product.name}")
        else:
            accommodation_product = self._get_or_create_accommodation_product()
            _logger.info(
                f"Produit hébergement créé/récupéré: {accommodation_product.name if accommodation_product else 'None'}")

        tax_product = None
        if config.get('tax_product_id'):
            tax_product = self.env['product.product'].browse(config['tax_product_id'])
            _logger.info(f"Produit taxe depuis config: {tax_product.name}")
        elif config.get('tax_product_id') is not False:  # Si pas explicitement désactivé
            tax_product = self._get_tourist_tax_product()
            _logger.info(f"Produit taxe récupéré: {tax_product.name if tax_product else 'None'}")

        invoice_lines = []
        _logger.info("Début création des lignes de facture")

        # Grouper les réservations par type d'hébergement et durée
        reservation_groups = {}
        for reservation in reservations:
            key = (reservation.property_type_id.id, reservation.duration_nights)
            if key not in reservation_groups:
                reservation_groups[key] = []
            reservation_groups[key].append(reservation)

        _logger.info(f"Groupes de réservations créés: {len(reservation_groups)}")

        # Créer les lignes de facture
        for (property_type_id, duration), group_reservations in reservation_groups.items():
            _logger.info(
                f"Traitement du groupe: property_type_id={property_type_id}, duration={duration}, {len(group_reservations)} réservations")

            property_type = self.env['product.template'].browse(property_type_id)

            # Calculer les totaux pour ce groupe
            total_guests = sum(res.pax_nb for res in group_reservations)
            total_nights = sum(res.duration_nights for res in group_reservations)
            total_nights_adults = sum(res.nights_adults for res in group_reservations)

            _logger.info(
                f"Totaux - guests: {total_guests}, nights: {total_nights}, nights_adults: {total_nights_adults}")

            # Ligne principale : hébergement
            # Utiliser le tarif du produit configuré ou le tarif moyen des réservations
            if accommodation_product.list_price > 0:
                unit_price = accommodation_product.list_price
                quantity = total_nights  # Facturer par nuitée
                _logger.info(f"Prix depuis produit: {unit_price}, quantité: {quantity}")
            else:
                # Utiliser les tarifs des réservations
                avg_rate = sum(res.rate for res in group_reservations if res.rate)
                if avg_rate > 0:
                    unit_price = avg_rate / len([res for res in group_reservations if res.rate])
                    quantity = len(group_reservations)
                    _logger.info(f"Prix calculé depuis réservations: {unit_price}, quantité: {quantity}")
                else:
                    unit_price = 10000.0  # Prix par défaut
                    quantity = total_nights
                    _logger.info(f"Prix par défaut: {unit_price}, quantité: {quantity}")

            description = f"Hébergement {property_type.name}"
            if len(group_reservations) > 1:
                description += f" - {len(group_reservations)} réservations"

            # Ajouter les détails des dates
            dates_info = []
            for res in group_reservations:
                date_str = res.arrival_date.strftime('%d/%m/%Y')
                dates_info.append(f"{date_str} ({res.duration_nights}n, {res.pax_nb}p)")

            description += f"\nDétail: {', '.join(dates_info)}"

            invoice_line_vals = {
                'product_id': accommodation_product.id,
                'name': description,
                'quantity': quantity,
                'price_unit': unit_price,
                'account_id': accommodation_product.property_account_income_id.id or
                              accommodation_product.categ_id.property_account_income_categ_id.id,
            }
            invoice_lines.append((0, 0, invoice_line_vals))
            _logger.info(f"Ligne hébergement ajoutée: {invoice_line_vals}")

            # Ligne taxe de séjour si applicable
            if total_nights_adults > 0 and tax_product:
                tax_line_vals = {
                    'product_id': tax_product.id,
                    'name': f"Taxe de séjour - {total_nights_adults} nuitées adultes",
                    'quantity': total_nights_adults,
                    'price_unit': tax_product.list_price,
                    'account_id': tax_product.property_account_income_id.id or
                                  tax_product.categ_id.property_account_income_id.id
                }
                invoice_lines.append((0, 0, tax_line_vals))
                _logger.info(f"Ligne taxe ajoutée: {tax_line_vals}")
            elif total_nights_adults > 0:
                _logger.info("Pas de ligne taxe car tax_product est None")
            else:
                _logger.info("Pas de ligne taxe car total_nights_adults = 0")

        _logger.info(f"Total lignes de facture créées: {len(invoice_lines)}")

        # ⚠️ PROBLÈME ICI : Il manque la création de la facture !
        _logger.warning("ATTENTION: Les lignes sont créées mais aucune facture n'est générée !")
        _logger.info("Il faut ajouter la création de l'account.move avec ces lignes")

        # Code manquant qui devrait être ajouté :
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': customer.id,
            'invoice_line_ids': invoice_lines,
            # autres champs nécessaires...
        }
        invoice = self.env['account.move'].create(invoice_vals)
        return invoice

        _logger.info("=== FIN _create_customer_invoice ===")
        # La méthode ne retourne rien actuellement !
        return None

    def _get_or_create_accommodation_product(self):
        """Récupère ou crée le produit pour l'hébergement"""

        # Chercher d'abord si le produit existe déjà
        product = self.env['product.product'].search([
            ('name', 'ilike', 'Hébergement'),
            ('type', '=', 'service'),
            ('sale_ok', '=', True)
        ], limit=1)

        if product:
            return product

        # Créer le produit s'il n'existe pas
        product = self.env['product.product'].create({
            'name': 'Hébergement touristique',
            'type': 'service',
            'sale_ok': True,
            'purchase_ok': False,
            'list_price': 10000.0,  # Prix par défaut en XPF
            'uom_id': self.env.ref('uom.product_uom_unit').id,
            'uom_po_id': self.env.ref('uom.product_uom_unit').id,
        })

        return product

    def _get_tourist_tax_product(self):
        """Récupère le produit taxe de séjour pour la facturation client"""

        # Utiliser le même produit que pour les déclarations trimestrielles si possible
        quarter_record = self.env['booking.quarter'].search([
            ('property_type_id', '=', self.property_type_id.id),
            ('year', '=', self.year),
        ], limit=1)

        if quarter_record and quarter_record.tourist_tax_product_id:
            # Créer un produit client basé sur le produit de taxe municipale
            tax_product_template = quarter_record.tourist_tax_product_id

            # Chercher s'il existe déjà un produit client pour la taxe
            client_tax_product = self.env['product.product'].search([
                ('name', 'ilike', 'Taxe de séjour'),
                ('type', '=', 'service'),
                ('sale_ok', '=', True)
            ], limit=1)

            if not client_tax_product:
                # Créer le produit client pour la taxe de séjour
                client_tax_product = self.env['product.product'].create({
                    'name': 'Taxe de séjour',
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'list_price': tax_product_template.list_price,
                    'uom_id': self.env.ref('uom.product_uom_unit').id,
                    'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                })

            return client_tax_product

        return None

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
    _logger.info("=== DÉBUT action_generate_all_invoices ===")
    _logger.info(f"Modèle: {self._name}, ID: {self.id}")
    _logger.info(f"customer_invoices_generated: {getattr(self, 'customer_invoices_generated', 'ATTRIBUT INEXISTANT')}")

    # Vérifier si la méthode parente existe
    try:
        _logger.info("Appel de super().action_generate_all_invoices()")
        result = super().action_generate_all_invoices()
        _logger.info(f"Retour de super(): {result}")
    except Exception as e:
        _logger.error(f"Erreur dans super().action_generate_all_invoices(): {e}")
        import traceback
        _logger.error(f"Traceback: {traceback.format_exc()}")
        raise

    # Ajouter la génération des factures clients si pas encore fait
    _logger.info("Vérification de customer_invoices_generated...")

    if not getattr(self, 'customer_invoices_generated', False):
        _logger.info("customer_invoices_generated = False, génération des factures clients...")
        try:
            _logger.info("Appel de self.action_generate_customer_invoices()")
            self.action_generate_customer_invoices()
            _logger.info("self.action_generate_customer_invoices() terminée avec succès")
        except Exception as e:
            _logger.warning(f"Erreur lors de la génération des factures clients: {str(e)}")
            import traceback
            _logger.warning(f"Traceback complet: {traceback.format_exc()}")
    else:
        _logger.info("customer_invoices_generated = True, génération ignorée")

    _logger.info("=== FIN action_generate_all_invoices ===")
    return result

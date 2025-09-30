from odoo import models, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BilletWebSyncProcessor(models.AbstractModel):
    _name = 'billetweb.sync.processor'
    _description = 'Traitement logique des transactions BilletWeb'

    def process_payout_line(self, company, payout_line, attendee_info, api_user, api_key):
        """Traite une ligne de virement et son participant lié (attendee)."""
        _logger.info(
            f"processor.process_payout_line : company.name={company.name}, attendee_info['name']={attendee_info.get('name', 'N/A')}.")

        try:
            # Créer un environnement avec la bonne société
            self_with_company = self.with_company(company)

            # 1. Client final (acheteur du billet)
            partner = self_with_company.find_or_create_partner(attendee_info)

            # 2. Evénement lié
            event = self.env['billetweb.sync.helper'].find_or_create_event(attendee_info, api_user, api_key)

            # 3. Vérifier si la facture existe déjà
            existing_invoice = self.env['account.move'].search([
                ('company_id', '=', company.id),
                ('partner_id', '=', partner.id),
                ('invoice_origin', '=', str(payout_line.order_id)),  # Accès comme attribut
                ('move_type', '=', 'out_invoice')
            ], limit=1)

            if existing_invoice:
                _logger.warning(f"Facture déjà existante pour Order ID {payout_line.order_id}.")
                return existing_invoice

            # 4. Créer la facture client
            invoice = self_with_company.create_invoice(partner, event, payout_line, attendee_info)

            # 5. Si payé ➔ Créer paiement
            if str(attendee_info.get('order_paid', '0')) == "1":
                payment = self_with_company.create_payment(invoice, payout_line)
                _logger.info(f"Paiement créé pour la facture {invoice.name}.")
            else:
                _logger.warning(
                    f"Commande non payée ou remboursée pour Order ID {payout_line.order_id}. Facture créée sans paiement.")

            # Mise à jour des statistiques
            self_with_company._update_event_stats(attendee_info, invoice)

            return invoice

        except Exception as e:
            _logger.error(f"Erreur lors du traitement de la ligne de paiement : {str(e)}")
            # Rollback de la transaction en cas d'erreur
            self.env.cr.rollback()
            raise

    def find_or_create_partner(self, attendee_info):
        """Trouve ou crée un res.partner basé sur l'email du participant."""
        _logger.info(
            f"processor.find_or_create_partner : attendee_info['order_email']={attendee_info.get('order_email', 'N/A')}")

        company = self.env.company
        _logger.info(f"processor.find_or_create_partner : company : {company.name}")

        email = attendee_info.get('order_email', '').strip()
        firstname = attendee_info.get('order_firstname', '').strip()
        lastname = attendee_info.get('order_name', '').strip()
        name = f"{firstname} {lastname}".strip()

        if not email:
            raise UserError("Email du client non fourni dans les données BilletWeb.")

        # Recherche du partenaire existant
        partner = self.env['res.partner'].search([
            ('email', '=', email),
            ('company_id', '=', company.id)
        ], limit=1)

        if not partner:
            partner_vals = {
                'name': name or email,
                'email': email,
                'customer_rank': 1,
                'company_id': company.id,
            }
            partner = self.env['res.partner'].create(partner_vals)
            _logger.info(f"Création d'un nouveau client : {partner.name} ({partner.email})")

        return partner

    def create_invoice(self, partner, event, payout_line, attendee_info):
        """Crée une facture client pour l'achat du billet."""
        _logger.info(
            f"processor.create_invoice : partner.name={partner.name}, partner.company_id.name={partner.company_id.name}.")

        try:
            # Validation des données - accès aux attributs d'objet Odoo
            price = float(payout_line.price or 0)
            if price <= 0:
                raise UserError(f"Prix invalide pour la commande {payout_line.order_id}")

            # Obtenir la taxe
            tax_id = self.get_tax_id(payout_line.tax_rate or '0', partner)

            move_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_origin': str(payout_line.order_id or ''),
                'invoice_date': fields.Date.today(),
                'company_id': partner.company_id.id,
                'currency_id': self.env.ref('base.EUR').id,
                'invoice_line_ids': [(0, 0, {
                    'name': f"{attendee_info.get('ticket', 'Billet')}",
                    'quantity': 1,
                    'price_unit': price,
                    'tax_ids': [(6, 0, [tax_id])] if tax_id else [],
                })],
            }

            invoice = self.env['account.move'].create(move_vals)
            invoice.action_post()
            _logger.info(f"Facture créée {invoice.name} pour {partner.name}.")
            return invoice

        except Exception as e:
            _logger.error(f"Erreur lors de la création de la facture : {str(e)}")
            raise

    def create_payment(self, invoice, payout_line):
        """Crée un paiement client lié à la facture."""
        _logger.info(
            f"processor.create_payment : invoice.partner_id.name={invoice.partner_id.name}, payout_line.date={payout_line.date or 'N/A'}.")

        try:
            payment_method = self.env.ref('account.account_payment_method_manual_in')
            payment_journal = self.env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', invoice.company_id.id)
            ], limit=1)

            if not payment_journal:
                raise UserError(f"Aucun journal bancaire trouvé pour la société {invoice.company_id.name}")

            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice.partner_id.id,
                'amount': invoice.amount_total,
                'date': payout_line.date or fields.Date.today(),
                'journal_id': payment_journal.id,
                'payment_method_id': payment_method.id,
                'currency_id': invoice.currency_id.id,
                'company_id': invoice.company_id.id,
            }

            payment = self.env['account.payment'].create(payment_vals)
            payment.action_post()

            # Réconciliation du paiement avec la facture
            # ERROR: payment.reconcile([invoice])
            # Todo
            # Paiement et facture doivent être validés
            # payment.action_post()
            # invoice.action_post()

            # Réconciliation via les lignes comptables
            # lines_to_reconcile = (payment.line_ids + invoice.line_ids).filtered(
            #     lambda l: l.account_id == invoice.line_ids[0].account_id and l.reconciled is False
            # )
            #
            # lines_to_reconcile.reconcile()

            return payment

        except Exception as e:
            _logger.error(f"Erreur lors de la création du paiement : {str(e)}")
            raise

    def get_tax_id(self, tax_rate_str, partner):
        """Trouve ou crée une taxe en fonction du taux donné."""
        _logger.info(f"processor.get_tax_id : tax_rate_str={tax_rate_str}, partner.name={partner.name}.")

        try:
            tax_rate = float(tax_rate_str or 0)

            if tax_rate == 0:
                return False  # Pas de taxe

            name = f"{tax_rate}% TVA"

            tax = self.env['account.tax'].search([
                ('amount', '=', tax_rate),
                ('type_tax_use', '=', 'sale'),
                ('company_id', '=', partner.company_id.id)
            ], limit=1)

            if not tax:
                tax_vals = {
                    'name': name,
                    'amount': tax_rate,
                    'type_tax_use': 'sale',
                    'company_id': partner.company_id.id,
                }
                tax = self.env['account.tax'].create(tax_vals)
                _logger.info(f"Taxe créée : {tax.name}")

            return tax.id

        except Exception as e:
            _logger.error(f"Erreur lors de la gestion de la taxe : {str(e)}")
            return False

    def _update_event_stats(self, attendee_info, invoice):
        """Met à jour les statistiques de l'événement."""
        try:
            stats = self.env['billetweb.event.stats'].search([
                ('event_id', '=', attendee_info.get('event'))
            ], limit=1)

            if not stats:
                stats_vals = {
                    'name': attendee_info.get('event_name', 'Événement'),
                    'event_id': attendee_info.get('event'),
                    'event_date': attendee_info.get('event_start'),
                    'company_id': invoice.company_id.id,
                    'currency_id': invoice.currency_id.id,
                }
                stats = self.env['billetweb.event.stats'].create(stats_vals)

            price = float(attendee_info.get('price', 0))

            if str(attendee_info.get('order_paid', '0')) == "1":
                stats.number_of_tickets += 1
                stats.amount_total += price
            else:
                stats.number_of_refunds += 1
                stats.amount_refunded += price

        except Exception as e:
            _logger.error(f"Erreur lors de la mise à jour des statistiques : {str(e)}")
            # Ne pas faire échouer le processus principal pour les statistiques

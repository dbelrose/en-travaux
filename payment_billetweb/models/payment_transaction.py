# -*- coding: utf-8 -*-

import logging
from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    billetweb_order_id = fields.Char(
        string="Billetweb Order ID",
        help="ID de la commande dans Billetweb",
        readonly=True
    )

    billetweb_event_id = fields.Char(
        string="Billetweb Event ID",
        help="ID de l'événement Billetweb associé",
        readonly=True
    )

    billetweb_shop_url = fields.Char(
        string="URL Boutique Billetweb",
        help="URL de paiement Billetweb",
        readonly=True
    )

    def _get_specific_rendering_values(self, processing_values):
        """
        Override pour retourner les valeurs de rendu spécifiques à Billetweb.

        :param dict processing_values: Valeurs de traitement de la transaction
        :return: Valeurs de rendu spécifiques au provider
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)

        if self.provider_code != 'billetweb':
            return res

        # Récupération de l'événement
        event_id = self.provider_id.billetweb_default_event_id
        if not event_id:
            raise ValidationError(
                _("Aucun événement Billetweb configuré. Veuillez configurer un Event ID dans les paramètres du provider."))

        # Préparation des données de commande
        order_data = self._billetweb_prepare_order_data(event_id)

        # Création de la commande sur Billetweb
        try:
            result = self.provider_id._api_billetweb_create_order(event_id, order_data)

            if result and len(result) > 0:
                order_info = result[0]
                billetweb_order_id = order_info.get('id')

                # Sauvegarde des informations
                self.write({
                    'billetweb_order_id': billetweb_order_id,
                    'billetweb_event_id': event_id,
                    'provider_reference': self.reference,
                })

                # Récupération de l'URL de la boutique
                event_details = self.provider_id._api_billetweb_get_event(event_id)
                shop_url = event_details.get('shop', '')

                if shop_url:
                    self.billetweb_shop_url = shop_url

                    return {
                        'api_url': shop_url,
                        'billetweb_order_id': billetweb_order_id,
                    }
                else:
                    raise ValidationError(_("Impossible de récupérer l'URL de paiement Billetweb"))
            else:
                raise ValidationError(_("Erreur lors de la création de la commande Billetweb"))

        except Exception as e:
            _logger.exception("Erreur lors de la création de la commande Billetweb")
            raise ValidationError(_("Erreur Billetweb: %s") % str(e))

    def _billetweb_prepare_order_data(self, event_id):
        """
        Prépare les données de commande pour l'API Billetweb.

        :param str event_id: ID de l'événement
        :return: Données de commande formatées
        :rtype: list
        """
        self.ensure_one()

        # Récupération des tarifs de l'événement
        tickets = self.provider_id._api_billetweb_get_event_tickets(event_id)

        if not tickets:
            raise ValidationError(_("Aucun tarif trouvé pour cet événement Billetweb"))

        # Sélection du premier tarif disponible (vous pouvez adapter cette logique)
        ticket = tickets[0]
        ticket_id = ticket.get('id')

        # Préparation des données
        order_data = [{
            'name': self.partner_name or self.partner_id.name,
            'firstname': self.partner_name.split()[0] if self.partner_name else self.partner_id.name,
            'email': self.partner_email or self.partner_id.email,
            'request_id': self.reference,
            'payment_type': 'card',
            'products': [{
                'ticket': ticket_id,
                'name': self.partner_name or self.partner_id.name,
                'firstname': self.partner_name.split()[0] if self.partner_name else self.partner_id.name,
                'email': self.partner_email or self.partner_id.email,
                'price': "%.2f" % self.amount,
                'request_id': f"{self.reference}_P1",
            }]
        }]

        return order_data

    def _process_notification_data(self, notification_data):
        """
        Traite les données de notification de Billetweb.

        :param dict notification_data: Données de notification
        :return: None
        """
        if self.provider_code != 'billetweb':
            return super()._process_notification_data(notification_data)

        if self.state == 'done':
            return

        # Vérification du statut de la commande
        try:
            order_details = self.provider_id._api_billetweb_get_order_details(
                self.billetweb_event_id,
                self.reference
            )

            if order_details:
                order_paid = order_details.get('order_paid', '0')

                if order_paid == '1':
                    # Paiement confirmé
                    self._set_done()
                    _logger.info(f"Transaction {self.reference} marquée comme payée")
                elif order_paid == '0':
                    # Paiement en attente ou échoué
                    disabled = order_details.get('disabled', '0')
                    if disabled == '1':
                        # Remboursé
                        self._set_canceled(_("Commande remboursée"))
                    else:
                        # En attente
                        self._set_pending()
                else:
                    self._set_error(_("Statut de paiement inconnu"))
            else:
                _logger.warning(f"Commande {self.reference} non trouvée dans Billetweb")
                self._set_pending()

        except Exception as e:
            _logger.exception(f"Erreur lors de la vérification du statut de la transaction {self.reference}")
            self._set_error(_("Erreur lors de la vérification: %s") % str(e))

    def _send_refund_request(self, amount_to_refund=None, create_refund_transaction=True):
        """
        Envoie une demande de remboursement à Billetweb.

        :param float amount_to_refund: Montant à rembourser
        :param bool create_refund_transaction: Créer une transaction de remboursement
        :return: Transaction de remboursement
        :rtype: recordset of payment.transaction
        """
        if self.provider_code != 'billetweb':
            return super()._send_refund_request(
                amount_to_refund=amount_to_refund,
                create_refund_transaction=create_refund_transaction
            )

        refund_tx = super()._send_refund_request(
            amount_to_refund=amount_to_refund,
            create_refund_transaction=True
        )

        try:
            # Remboursement via l'API Billetweb
            if self.billetweb_order_id:
                result = self.provider_id._api_billetweb_refund_order(self.billetweb_order_id)
                _logger.info(f"Remboursement effectué pour la commande {self.billetweb_order_id}")

                # Mise à jour de la transaction de remboursement
                if refund_tx:
                    refund_tx.write({
                        'provider_reference': f"refund_{self.billetweb_order_id}",
                    })
                    refund_tx._set_done()
            else:
                raise ValidationError(_("Aucun ID de commande Billetweb trouvé"))

        except Exception as e:
            _logger.exception(f"Erreur lors du remboursement de la transaction {self.reference}")
            if refund_tx:
                refund_tx._set_error(_("Erreur de remboursement: %s") % str(e))
            raise

        return refund_tx

    def _cron_finalize_post_processing(self):
        """
        Cron pour finaliser le post-traitement des transactions.
        Vérifie périodiquement le statut des transactions en attente.
        """
        super()._cron_finalize_post_processing()

        # Transactions Billetweb en attente
        pending_txs = self.search([
            ('provider_code', '=', 'billetweb'),
            ('state', 'in', ['pending', 'draft']),
            ('billetweb_event_id', '!=', False),
        ])

        for tx in pending_txs:
            try:
                tx._process_notification_data({})
            except Exception as e:
                _logger.exception(f"Erreur lors de la vérification du statut de {tx.reference}")
                continue

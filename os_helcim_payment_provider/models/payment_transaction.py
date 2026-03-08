# -*- coding: utf-8 -*-
import hashlib
import json
import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    helcim_transaction_id = fields.Char(
        string='ID Transaction Helcim',
        readonly=True,
        help='Identifiant unique de la transaction dans le système Helcim.',
    )
    helcim_checkout_token = fields.Char(
        string='Checkout Token Helcim',
        readonly=True,
        groups='base.group_system',
        help='Token de session HelcimPay.js utilisé pour l\'affichage du modal.',
    )
    helcim_secret_token = fields.Char(
        string='Secret Token Helcim',
        readonly=True,
        groups='base.group_system',
        help='Secret Token pour la validation HMAC de la réponse de transaction.',
    )
    helcim_card_type = fields.Char(
        string='Type de carte',
        readonly=True,
    )
    helcim_card_number = fields.Char(
        string='Numéro de carte (masqué)',
        readonly=True,
        help='Ex: 4111XXXXXXXX1111',
    )
    helcim_approval_code = fields.Char(
        string='Code d\'approbation',
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # Initialisation du paiement : création de la session HelcimPay.js
    # -------------------------------------------------------------------------
    def _get_specific_rendering_values(self, processing_values):
        """
        Initialise la session HelcimPay.js et retourne les valeurs pour le template.
        Appelé par Odoo pour obtenir les paramètres du formulaire de paiement.
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'helcim':
            return res

        provider = self.provider_id

        # Calcul du montant selon la devise
        # XPF (Franc CFP) est une devise sans décimale (ISO 4217 : exposant 0)
        # Helcim attend le montant en unité majeure (ex: 1500.00 pour 1500 XPF)
        amount = self.amount
        currency_name = self.currency_id.name or provider.helcim_currency_iso

        try:
            session_data = provider._helcim_initialize_checkout_session(
                amount=amount,
                currency_name=currency_name,
                reference=self.reference,
            )
        except ValidationError as e:
            _logger.error("Helcim: Impossible d'initialiser la session - %s", e)
            raise

        checkout_token = session_data.get('checkoutToken')
        secret_token = session_data.get('secretToken')

        if not checkout_token or not secret_token:
            raise ValidationError(
                _("Helcim: La réponse d'initialisation ne contient pas les tokens attendus. "
                  "Réponse reçue: %s") % session_data
            )

        # Sauvegarde des tokens pour la validation ultérieure
        self.write({
            'helcim_checkout_token': checkout_token,
            'helcim_secret_token': secret_token,
        })

        return {
            'checkout_token': checkout_token,
            'return_url': '/payment/helcim/return',
            'reference': self.reference,
        }

    # -------------------------------------------------------------------------
    # Traitement de la réponse de paiement
    # -------------------------------------------------------------------------
    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Retrouve la transaction à partir des données de retour Helcim."""
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'helcim' or len(tx) == 1:
            return tx

        reference = notification_data.get('invoiceNumber') or notification_data.get('customerCode')
        if not reference:
            raise ValidationError(
                _("Helcim: Données de retour invalides - référence manquante.")
            )

        tx = self.search([
            ('reference', '=', reference),
            ('provider_code', '=', 'helcim'),
        ])
        if not tx:
            raise ValidationError(
                _("Helcim: Aucune transaction trouvée pour la référence '%s'.") % reference
            )
        return tx

    def _process_notification_data(self, notification_data):
        """
        Traite les données de notification HelcimPay.js et met à jour la transaction.
        Valide la signature HMAC avant tout traitement.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'helcim':
            return

        _logger.info(
            "Helcim: Traitement notification pour transaction %s - données: %s",
            self.reference, notification_data
        )

        # Validation HMAC de la réponse
        if not self._helcim_validate_transaction_hash(notification_data):
            _logger.error(
                "Helcim: Validation HMAC échouée pour la transaction %s", self.reference
            )
            self._set_error("Helcim: Validation de la réponse de paiement échouée (HMAC invalide).")
            return

        transaction_status = notification_data.get('status', '').upper()
        helcim_tx_id = str(notification_data.get('transactionId', ''))
        card_type = notification_data.get('cardType', '')
        card_number = notification_data.get('cardNumber', '')
        approval_code = notification_data.get('approvalCode', '')

        # Mise à jour des informations de transaction
        self.write({
            'helcim_transaction_id': helcim_tx_id,
            'helcim_card_type': card_type,
            'helcim_card_number': card_number,
            'helcim_approval_code': approval_code,
        })

        if transaction_status == 'APPROVED':
            _logger.info(
                "Helcim: Transaction %s approuvée (Helcim ID: %s, Code: %s)",
                self.reference, helcim_tx_id, approval_code
            )
            self._set_done()
        elif transaction_status == 'DECLINED':
            error_detail = notification_data.get('errors', _('Paiement refusé par la banque.'))
            _logger.warning(
                "Helcim: Transaction %s refusée - %s", self.reference, error_detail
            )
            self._set_canceled(
                state_message=_("Paiement refusé par Helcim: %s") % error_detail
            )
        else:
            _logger.warning(
                "Helcim: Statut inconnu '%s' pour la transaction %s",
                transaction_status, self.reference
            )
            self._set_pending()

    def _helcim_validate_transaction_hash(self, transaction_data):
        """
        Valide le hash HMAC SHA-256 de la réponse HelcimPay.js.

        Méthode de validation officielle Helcim :
        1. Encoder les données de transaction en JSON
        2. Concaténer avec le secretToken
        3. Hasher en SHA-256
        4. Comparer avec le hash retourné dans la réponse

        :param dict transaction_data: Les données de la réponse HelcimPay.js
        :return bool: True si le hash est valide, False sinon
        """
        self.ensure_one()

        received_hash = transaction_data.get('hash')
        if not received_hash:
            _logger.warning("Helcim: Aucun hash dans les données de transaction - ignoré en mode test")
            # En mode test, Helcim peut ne pas toujours envoyer un hash
            if self.provider_id.state == 'test':
                return True
            return False

        secret_token = self.helcim_secret_token
        if not secret_token:
            _logger.error("Helcim: Secret token manquant pour la transaction %s", self.reference)
            return False

        # Construction des données à hasher (sans le champ 'hash' lui-même)
        data_to_hash = {k: v for k, v in transaction_data.items() if k != 'hash'}
        json_data = json.dumps(data_to_hash, separators=(',', ':'), sort_keys=True)
        raw = json_data + secret_token

        computed_hash = hashlib.sha256(raw.encode('utf-8')).hexdigest()

        if computed_hash != received_hash:
            _logger.error(
                "Helcim: Hash invalide pour transaction %s. Attendu: %s, Reçu: %s",
                self.reference, computed_hash, received_hash
            )
            return False

        return True

    # -------------------------------------------------------------------------
    # Remboursements
    # -------------------------------------------------------------------------
    def _send_refund_request(self, amount_to_refund=None):
        """
        Effectue un remboursement via l'API Helcim.
        Utilise 'reverse' si la transaction est dans un batch ouvert,
        sinon utilise 'refund'.
        """
        refund_tx = super()._send_refund_request(amount_to_refund=amount_to_refund)
        if self.provider_code != 'helcim':
            return refund_tx

        if not self.helcim_transaction_id:
            raise ValidationError(
                _("Helcim: Impossible de rembourser - ID de transaction Helcim manquant.")
            )

        amount = amount_to_refund or self.amount
        provider = self.provider_id

        # Tentative de reverse d'abord (pour les transactions en batch ouvert)
        try:
            response = provider._helcim_make_request(
                f'/card-transactions/{self.helcim_transaction_id}/reverse',
                payload={'amount': float(amount)},
            )
            _logger.info(
                "Helcim: Reverse effectué pour transaction %s (Helcim ID: %s)",
                self.reference, self.helcim_transaction_id
            )
        except ValidationError:
            # Si le reverse échoue (batch fermé), on tente un refund
            _logger.info(
                "Helcim: Reverse impossible, tentative de refund pour transaction %s",
                self.reference
            )
            try:
                response = provider._helcim_make_request(
                    f'/card-transactions/{self.helcim_transaction_id}/refund',
                    payload={'amount': float(amount)},
                )
                _logger.info(
                    "Helcim: Refund effectué pour transaction %s", self.reference
                )
            except ValidationError as e:
                _logger.error("Helcim: Échec du remboursement - %s", e)
                raise

        if response.get('status', '').upper() == 'APPROVED':
            refund_tx._set_done()
        else:
            refund_tx._set_error(
                _("Helcim: Le remboursement a échoué: %s") % response.get('errors', '')
            )

        return refund_tx

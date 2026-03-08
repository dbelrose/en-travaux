# -*- coding: utf-8 -*-
import json
import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HelcimController(http.Controller):
    """
    Contrôleur HTTP pour gérer les retours de paiement HelcimPay.js.

    HelcimPay.js fonctionne via un modal iframe qui communique avec la page parent
    par postMessage (JavaScript). Ce contrôleur gère :
    - La page de retour après paiement (pour les flux non-JS)
    - L'endpoint de validation côté serveur appelé par le JS de la page
    """

    _return_url = '/payment/helcim/return'
    _webhook_url = '/payment/helcim/webhook'

    @http.route(
        _return_url,
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
        save_session=False,
    )
    def helcim_return(self, **data):
        """
        Endpoint de retour après paiement HelcimPay.js.
        Redirige vers la page de confirmation de paiement Odoo standard.
        """
        _logger.info("Helcim: Retour de paiement reçu - données: %s", pprint.pformat(data))
        return request.redirect('/payment/status')

    @http.route(
        '/payment/helcim/validate',
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def helcim_validate_payment(self, **data):
        """
        Endpoint JSON appelé par le JavaScript de la page de paiement
        pour valider la réponse de HelcimPay.js côté serveur.

        Reçoit les données de transaction depuis l'événement postMessage
        du modal HelcimPay.js et déclenche le traitement Odoo.
        """
        _logger.info(
            "Helcim: Validation de paiement reçue - données: %s",
            pprint.pformat(data)
        )

        transaction_data = data.get('transaction_data', {})
        reference = data.get('reference')

        if not reference:
            _logger.error("Helcim: Validation sans référence de transaction")
            return {'success': False, 'error': 'Référence de transaction manquante'}

        try:
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference),
                ('provider_code', '=', 'helcim'),
            ], limit=1)

            if not tx_sudo:
                _logger.error("Helcim: Transaction introuvable pour référence=%s", reference)
                return {'success': False, 'error': f'Transaction {reference} introuvable'}

            tx_sudo._process_notification_data(transaction_data)
            return {'success': True, 'state': tx_sudo.state}

        except ValidationError as e:
            _logger.exception("Helcim: Erreur de validation - %s", e)
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception("Helcim: Erreur inattendue lors de la validation - %s", e)
            return {'success': False, 'error': 'Erreur interne du serveur'}

    @http.route(
        _webhook_url,
        type='json',
        auth='public',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def helcim_webhook(self, **data):
        """
        Webhook Helcim pour les notifications asynchrones.
        Configure l'URL dans votre compte Helcim :
        https://api.helcim.com/v2/webhooks
        """
        _logger.info("Helcim: Webhook reçu - %s", pprint.pformat(data))

        event_type = data.get('eventType')
        event_data = data.get('data', {})

        if event_type == 'transaction.created':
            transaction_id = event_data.get('transactionId')
            customer_code = event_data.get('customerCode')

            if customer_code:
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', customer_code),
                    ('provider_code', '=', 'helcim'),
                ], limit=1)
                if tx_sudo:
                    tx_sudo._process_notification_data(event_data)

        return {'received': True}

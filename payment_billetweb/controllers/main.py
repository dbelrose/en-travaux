# -*- coding: utf-8 -*-

import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BilletwebController(http.Controller):
    _return_url = '/payment/billetweb/return'
    _webhook_url = '/payment/billetweb/webhook'

    @http.route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def billetweb_return_from_checkout(self, **data):
        """
        Route de retour après le paiement Billetweb.

        :param dict data: Données de retour
        """
        _logger.info("Retour depuis Billetweb avec données:\n%s", pprint.pformat(data))

        # Récupération de la référence de transaction
        tx_ref = data.get('ref') or data.get('reference')

        if not tx_ref:
            _logger.warning("Retour Billetweb sans référence de transaction")
            return request.redirect('/payment/status')

        # Récupération de la transaction
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', tx_ref),
            ('provider_code', '=', 'billetweb')
        ], limit=1)

        if not tx_sudo:
            _logger.warning(f"Transaction {tx_ref} non trouvée")
            return request.redirect('/payment/status')

        # Traitement de la notification
        try:
            tx_sudo._process_notification_data(data)
        except Exception as e:
            _logger.exception(f"Erreur lors du traitement de la notification pour {tx_ref}")

        # Redirection vers la landing route
        return request.redirect(tx_sudo.landing_route or '/payment/status')

    @http.route(_webhook_url, type='json', auth='public', methods=['POST'], csrf=False)
    def billetweb_webhook(self, **data):
        """
        Webhook pour recevoir les notifications de Billetweb.

        Note: Billetweb n'a pas de système de webhook natif,
        cette route est préparée au cas où vous configureriez
        un système de notification personnalisé.

        :param dict data: Données du webhook
        """
        _logger.info("Webhook Billetweb reçu:\n%s", pprint.pformat(data))

        try:
            # Récupération de la référence
            tx_ref = data.get('reference') or data.get('order_ext_id')

            if not tx_ref:
                _logger.warning("Webhook sans référence de transaction")
                return {'status': 'error', 'message': 'No reference provided'}

            # Recherche de la transaction
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('reference', '=', tx_ref),
                ('provider_code', '=', 'billetweb')
            ], limit=1)

            if not tx_sudo:
                _logger.warning(f"Transaction {tx_ref} non trouvée pour le webhook")
                return {'status': 'error', 'message': 'Transaction not found'}

            # Traitement des données
            tx_sudo._process_notification_data(data)

            return {'status': 'ok'}

        except Exception as e:
            _logger.exception("Erreur lors du traitement du webhook Billetweb")
            return {'status': 'error', 'message': str(e)}

    @http.route('/payment/billetweb/validate/<string:tx_reference>', type='http', auth='public', methods=['GET'],
                csrf=False)
    def billetweb_validate_transaction(self, tx_reference, **kwargs):
        """
        Route pour vérifier manuellement le statut d'une transaction.

        :param str tx_reference: Référence de la transaction
        """
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('reference', '=', tx_reference),
            ('provider_code', '=', 'billetweb')
        ], limit=1)

        if not tx_sudo:
            return request.redirect('/payment/status')

        try:
            tx_sudo._process_notification_data({})
        except Exception as e:
            _logger.exception(f"Erreur lors de la validation de {tx_reference}")

        return request.redirect(tx_sudo.landing_route or '/payment/status')

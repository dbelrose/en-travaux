# -*- coding: utf-8 -*-

import json
import logging
import requests
import base64
from werkzeug import urls

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('billetweb', 'Billetweb')],
        ondelete={'billetweb': 'set default'}
    )

    billetweb_user_id = fields.Char(
        string="Billetweb User ID",
        help="Votre identifiant utilisateur Billetweb",
        required_if_provider='billetweb',
        groups="base.group_system"
    )

    billetweb_api_key = fields.Char(
        string="Billetweb API Key",
        help="Votre clé API Billetweb",
        required_if_provider='billetweb',
        groups="base.group_system"
    )

    billetweb_default_event_id = fields.Char(
        string="Event ID par défaut",
        help="ID de l'événement Billetweb à utiliser par défaut pour les paiements",
        groups="base.group_user"
    )

    # ----------------
    # PAYMENT FEATURES
    # ----------------

    def _compute_feature_support_fields(self):
        """Override pour activer les fonctionnalités supportées."""
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'billetweb').update({
            'support_refund': 'full_only',
            'support_tokenization': False,
            'support_manual_capture': False,
        })

    # -----------
    # API METHODS
    # -----------

    def _billetweb_make_request(self, endpoint, params=None, data=None, method='GET'):
        """
        Effectue une requête vers l'API Billetweb.

        :param str endpoint: Le endpoint à appeler
        :param dict params: Les paramètres de la requête
        :param dict data: Les données à envoyer (pour POST/PUT)
        :param str method: La méthode HTTP
        :return: La réponse JSON
        :rtype: dict
        """
        self.ensure_one()

        # Construction de l'URL
        base_url = 'https://www.billetweb.fr/api'
        url = urls.url_join(base_url, endpoint.strip('/'))

        # Paramètres d'authentification
        auth_params = {
            'user': self.billetweb_user_id,
            'key': self.billetweb_api_key,
            'version': '1'
        }

        if params:
            auth_params.update(params)

        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        # Préparation des données
        if data and method in ['POST', 'PUT', 'PATCH']:
            data = json.dumps({'data': data})

        try:
            response = requests.request(
                method=method,
                url=url,
                params=auth_params,
                data=data,
                headers=headers,
                timeout=60
            )

            # Gestion des erreurs HTTP
            if response.status_code not in [200, 201]:
                error_msg = f"Billetweb API Error [{response.status_code}]: {response.text}"
                _logger.error(error_msg)
                raise ValidationError(_(error_msg))

            # Si pas de contenu
            if response.status_code == 204 or not response.content:
                return True

            result = response.json()
            return result

        except requests.exceptions.RequestException as e:
            error_msg = f"Erreur de connexion à l'API Billetweb: {str(e)}"
            _logger.exception(error_msg)
            raise ValidationError(_("Billetweb: ") + error_msg)

    def _api_billetweb_get_events(self, past=False):
        """
        Récupère la liste des événements.

        :param bool past: Inclure les événements passés
        :return: Liste des événements
        :rtype: list
        """
        params = {}
        if past:
            params['past'] = '1'

        return self._billetweb_make_request('/events', params=params)

    def _api_billetweb_get_event(self, event_id):
        """
        Récupère les détails d'un événement.

        :param str event_id: ID de l'événement
        :return: Détails de l'événement
        :rtype: dict
        """
        events = self._api_billetweb_get_events()
        for event in events:
            if str(event.get('id')) == str(event_id):
                return event
        return {}

    def _api_billetweb_get_event_tickets(self, event_id):
        """
        Récupère les tarifs d'un événement.

        :param str event_id: ID de l'événement
        :return: Liste des tarifs
        :rtype: list
        """
        endpoint = f'/event/{event_id}/tickets'
        return self._billetweb_make_request(endpoint)

    def _api_billetweb_create_order(self, event_id, order_data):
        """
        Crée une commande sur Billetweb.

        :param str event_id: ID de l'événement
        :param list order_data: Données de la commande
        :return: Réponse de l'API
        :rtype: list
        """
        endpoint = f'/event/{event_id}/attendees'
        return self._billetweb_make_request(endpoint, data=order_data, method='POST')

    def _api_billetweb_get_attendees(self, event_id, last_update=None):
        """
        Récupère les participants d'un événement.

        :param str event_id: ID de l'événement
        :param int last_update: Timestamp de dernière mise à jour
        :return: Liste des participants
        :rtype: list
        """
        endpoint = f'/event/{event_id}/attendees'
        params = {}
        if last_update:
            params['last_update'] = str(last_update)

        return self._billetweb_make_request(endpoint, params=params)

    def _api_billetweb_refund_order(self, order_id):
        """
        Rembourse une commande.

        :param str order_id: ID de la commande Billetweb
        :return: Résultat du remboursement
        :rtype: dict
        """
        endpoint = f'/attendees/refund'
        data = [{'id': order_id}]
        return self._billetweb_make_request(endpoint, data=data, method='POST')

    def _api_billetweb_validate_payment(self, order_id, payment_type='card'):
        """
        Valide le paiement d'une commande.

        :param str order_id: ID de la commande Billetweb
        :param str payment_type: Type de paiement
        :return: Résultat de la validation
        :rtype: dict
        """
        endpoint = f'/attendees/validate'
        data = [{
            'id': order_id,
            'payment_type': payment_type,
            'notification': '1'
        }]
        return self._billetweb_make_request(endpoint, data=data, method='POST')

    def _api_billetweb_get_order_details(self, event_id, order_ext_id):
        """
        Récupère les détails d'une commande via son ext_id.

        :param str event_id: ID de l'événement
        :param str order_ext_id: ID externe de la commande
        :return: Détails de la commande
        :rtype: dict
        """
        attendees = self._api_billetweb_get_attendees(event_id)
        for attendee in attendees:
            if attendee.get('order_ext_id') == order_ext_id:
                return attendee
        return {}

    # --------------
    # ACTION METHODS
    # --------------

    def action_sync_billetweb_events(self):
        """Synchronise les événements Billetweb."""
        self.ensure_one()
        events = self._api_billetweb_get_events()
        _logger.info(f"Synchronisé {len(events)} événements depuis Billetweb")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synchronisation réussie'),
                'message': _('%s événements synchronisés') % len(events),
                'type': 'success',
            }
        }

    # -------------------------
    # HELPER METHODS
    # -------------------------

    def _get_default_payment_method_codes(self):
        """Override pour ajouter les méthodes de paiement Billetweb."""
        codes = super()._get_default_payment_method_codes()
        if self.code == 'billetweb':
            codes.append('billetweb')
        return codes

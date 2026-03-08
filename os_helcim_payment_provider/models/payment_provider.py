# -*- coding: utf-8 -*-
import logging
import requests

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Endpoints Helcim API v2
HELCIM_API_URL = 'https://api.helcim.com/v2'
HELCIM_CHECKOUT_INIT_ENDPOINT = '/helcim-pay/initialize'
HELCIM_CONNECTION_TEST_ENDPOINT = '/connection-test'
HELCIM_TRANSACTION_ENDPOINT = '/card-transactions'
HELCIM_REFUND_ENDPOINT = '/card-transactions/{transaction_id}/refund'
HELCIM_REVERSE_ENDPOINT = '/card-transactions/{transaction_id}/reverse'


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('helcim', 'Helcim')],
        ondelete={'helcim': 'set default'},
    )

    # -------------------------------------------------------------------------
    # Champs spécifiques Helcim
    # -------------------------------------------------------------------------
    helcim_api_token = fields.Char(
        string='Jeton API Helcim',
        required_if_provider='helcim',
        groups='base.group_system',
        help='Votre jeton d\'accès API Helcim (api-token). '
             'Générez-le depuis votre compte Helcim > Paramètres > API.',
    )
    helcim_terminal_id = fields.Char(
        string='ID Terminal (optionnel)',
        groups='base.group_system',
        help='Identifiant du terminal carte Helcim à utiliser pour les paiements. '
             'Laissez vide pour utiliser le terminal par défaut.',
    )
    helcim_currency_iso = fields.Char(
        string='Code devise ISO',
        default='XPF',
        required_if_provider='helcim',
        help='Code ISO 4217 de la devise (ex: XPF pour le Franc CFP en Polynésie française, '
             'CAD pour le dollar canadien, USD pour le dollar américain).',
    )

    # -------------------------------------------------------------------------
    # Contraintes & calculs
    # -------------------------------------------------------------------------
    @api.constrains('helcim_currency_iso')
    def _check_helcim_currency_iso(self):
        for provider in self:
            if provider.code == 'helcim' and provider.helcim_currency_iso:
                if len(provider.helcim_currency_iso) != 3:
                    raise ValidationError(
                        _('Le code devise ISO doit faire exactement 3 caractères (ex: XPF, CAD, USD).')
                    )

    def _compute_feature_support_fields(self):
        """Déclare les fonctionnalités supportées par Helcim (Odoo 17)."""
        super()._compute_feature_support_fields()
        for provider in self.filtered(lambda p: p.code == 'helcim'):
            provider.support_refund = 'partial'
            provider.support_manual_capture = False
            provider.support_express_checkout = False
            provider.support_tokenization = False

    # -------------------------------------------------------------------------
    # Méthodes de configuration de la vue
    # -------------------------------------------------------------------------
    def _get_default_payment_method_codes(self):
        """Retourne les codes des méthodes de paiement par défaut pour Helcim."""
        default_codes = super()._get_default_payment_method_codes()
        if self.code != 'helcim':
            return default_codes
        return ['card']

    # -------------------------------------------------------------------------
    # API Helcim : Initialisation de session HelcimPay.js
    # -------------------------------------------------------------------------
    def _helcim_get_api_headers(self):
        """Retourne les en-têtes HTTP pour les appels à l'API Helcim."""
        self.ensure_one()
        return {
            'accept': 'application/json',
            'content-type': 'application/json',
            'api-token': self.helcim_api_token,
        }

    def _helcim_make_request(self, endpoint, payload=None, method='POST'):
        """
        Effectue un appel à l'API Helcim.

        :param str endpoint: Le chemin de l'endpoint (ex: '/helcim-pay/initialize')
        :param dict payload: Les données JSON à envoyer
        :param str method: La méthode HTTP ('POST', 'GET')
        :return dict: La réponse JSON de l'API
        :raises ValidationError: Si la requête échoue
        """
        self.ensure_one()
        url = f"{HELCIM_API_URL}{endpoint}"
        headers = self._helcim_get_api_headers()

        try:
            if method == 'POST':
                response = requests.post(url, json=payload, headers=headers, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            _logger.exception("Helcim: Erreur de connexion à l'API Helcim (%s)", url)
            raise ValidationError(
                _("Impossible de contacter l'API Helcim. Vérifiez votre connexion internet.")
            )
        except requests.exceptions.Timeout:
            _logger.exception("Helcim: Timeout lors de l'appel à l'API Helcim (%s)", url)
            raise ValidationError(
                _("L'API Helcim n'a pas répondu dans les délais impartis. Veuillez réessayer.")
            )
        except requests.exceptions.HTTPError as e:
            error_msg = ''
            try:
                error_data = response.json()
                error_msg = error_data.get('errors', str(e))
            except Exception:
                error_msg = str(e)
            _logger.exception("Helcim: Erreur HTTP %s - %s", response.status_code, error_msg)
            raise ValidationError(
                _("Erreur API Helcim (HTTP %s): %s") % (response.status_code, error_msg)
            )

    def _helcim_initialize_checkout_session(self, amount, currency_name, reference):
        """
        Initialise une session de paiement HelcimPay.js côté serveur.

        Retourne le checkoutToken (pour le frontend) et le secretToken (pour la validation).

        :param float amount: Le montant en unités entières (ex: 1500 pour 1500 XPF)
        :param str currency_name: Le code ISO de la devise
        :param str reference: La référence de la transaction Odoo
        :return dict: {'checkoutToken': ..., 'secretToken': ...}
        """
        self.ensure_one()

        payload = {
            'paymentType': 'purchase',
            'amount': float(amount),
            'currency': currency_name.upper(),
            'customerCode': reference,
        }

        if self.helcim_terminal_id:
            payload['cardTerminalId'] = int(self.helcim_terminal_id)

        _logger.info(
            "Helcim: Initialisation session checkout pour référence=%s, montant=%s %s",
            reference, amount, currency_name
        )

        response = self._helcim_make_request(HELCIM_CHECKOUT_INIT_ENDPOINT, payload)
        return response

    def _helcim_test_connection(self):
        """Teste la connexion à l'API Helcim avec le token configuré."""
        self.ensure_one()
        try:
            self._helcim_make_request(HELCIM_CONNECTION_TEST_ENDPOINT, method='GET')
            return True
        except ValidationError:
            return False

    # -------------------------------------------------------------------------
    # Override de la méthode de rendu du formulaire de paiement
    # -------------------------------------------------------------------------
    def _get_redirect_form_view(self, is_validation=False):
        """Retourne la vue du formulaire de redirection Helcim."""
        if self.code != 'helcim':
            return super()._get_redirect_form_view(is_validation)
        return self.env.ref('os_helcim_payment_provider.helcim_redirect_form')

    def action_helcim_test_connection(self):
        """Action bouton : Tester la connexion à l'API Helcim."""
        self.ensure_one()
        if self.code != 'helcim':
            return
        if self._helcim_test_connection():
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connexion réussie'),
                    'message': _('La connexion à l\'API Helcim est opérationnelle.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Échec de connexion'),
                    'message': _('Impossible de se connecter à l\'API Helcim. '
                                 'Vérifiez votre jeton API.'),
                    'type': 'danger',
                    'sticky': True,
                },
            }

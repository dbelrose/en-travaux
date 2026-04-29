from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class OsContactEncryptedController(http.Controller):
    """
    Contrôleur léger : expose un endpoint JSON pour que le frontend
    sache si l'utilisateur connecté doit initialiser ses clés.
    Utilisé par le widget JS pour afficher une notification Odoo.
    """

    @http.route(
        '/os_contact_encrypted/check_keys',
        type='json',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def check_keys(self):
        user = request.env.user
        has_keys = bool(user.rsa_public_key)
        return {
            'has_keys': has_keys,
            'user_name': user.name,
        }

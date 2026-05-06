from odoo import models, fields, api, exceptions
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from typing import Optional

import os, struct
import base64
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    # ── Clés RSA ──────────────────────────────────────────────────────────────
    rsa_public_key = fields.Text(
        string='Clé publique RSA',
        readonly=True,
        groups='os_contact_encrypted.group_crypto_admin,base.group_user',
    )
    rsa_private_key_enc = fields.Text(
        string='Clé privée (chiffrée)',
        readonly=True,
        groups='os_contact_encrypted.group_crypto_admin,base.group_user',
    )
    emergency_key_enc = fields.Text(
        string='Clé d\'urgence (chiffrée admin)',
        readonly=True,
        groups='os_contact_encrypted.group_crypto_admin',
    )
    has_crypto_keys = fields.Boolean(
        string='Chiffrement initialisé',
        compute='_compute_has_crypto_keys',
    )

    # ── Préférences de chiffrement par champ ──────────────────────────────────
    encrypted_field_pref_ids = fields.One2many(
        'user.encrypted.field.pref',
        'user_id',
        string='Champs à chiffrer',
    )

    @api.depends('rsa_public_key')
    def _compute_has_crypto_keys(self):
        for user in self:
            user.has_crypto_keys = bool(user.rsa_public_key)

    # ── Initialisation des préférences par défaut ─────────────────────────────
    def _init_default_field_prefs(self):
        """
        Crée les préférences utilisateur par défaut à partir de la config admin.
        Appelé lors de l'initialisation des clés RSA.
        """
        Config = self.env['encrypted.field.config'].sudo()
        Pref = self.env['user.encrypted.field.pref'].sudo()
        active_fields = Config.get_active_fields()

        existing = Pref.search([('user_id', '=', self.id)]).mapped('field_name')
        to_create = [
            {'user_id': self.id, 'field_name': f, 'enabled': True}
            for f in active_fields if f not in existing
        ]
        if to_create:
            Pref.create(to_create)

    # ── Génération de la paire RSA ────────────────────────────────────────────
    def generate_rsa_keypair(self, password: str):
        self.ensure_one()
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        encrypted_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode('utf-8')
            ),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        vals = {
            'rsa_public_key': public_pem.decode('utf-8'),
            'rsa_private_key_enc': base64.b64encode(encrypted_private).decode('utf-8'),
        }
        emergency_key_enc = self._build_emergency_key(encrypted_private)
        if emergency_key_enc:
            vals['emergency_key_enc'] = emergency_key_enc

        self.sudo().write(vals)

        # Initialiser les préférences de champs si pas encore créées
        self._init_default_field_prefs()

        _logger.info('[os_contact_encrypted] Paire RSA générée pour %s (id=%s)', self.login, self.id)

    def _build_emergency_key(self, encrypted_private_pem: bytes) -> Optional[str]:
        """
        Chiffrement hybride :
        1. Génère une clé AES-256 éphémère
        2. Chiffre le PEM avec AES-256-CBC
        3. Chiffre la clé AES avec RSA-4096/OAEP (≤ 446 octets → OK)
        4. Stocke : [len_rsa_blob(4)][rsa_blob][iv(16)][aes_ciphertext]
        """

        ICP = self.env['ir.config_parameter'].sudo()
        admin_pub_pem = ICP.get_param('os_contact_encrypted.emergency_admin_public_key')
        if not admin_pub_pem:
            return None
        try:
            admin_pub_key = serialization.load_pem_public_key(
                admin_pub_pem.encode('utf-8'),
                backend=default_backend(),
            )
            # 1. Clé AES éphémère
            aes_key = os.urandom(32)  # AES-256
            iv = os.urandom(16)

            # 2. Chiffrement AES du PEM (padding PKCS7 manuel)
            pad_len = 16 - (len(encrypted_private_pem) % 16)
            padded = encrypted_private_pem + bytes([pad_len] * pad_len)
            cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
            enc = cipher.encryptor()
            aes_ciphertext = enc.update(padded) + enc.finalize()

            # 3. Chiffrement RSA de la clé AES (32 octets << 446 → OK)
            rsa_blob = admin_pub_key.encrypt(
                aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            # 4. Assemblage : 4 octets longueur RSA | blob RSA | IV | ciphertext AES
            payload = struct.pack('>I', len(rsa_blob)) + rsa_blob + iv + aes_ciphertext
            return base64.b64encode(payload).decode('utf-8')

        except Exception as e:
            _logger.warning('[os_contact_encrypted] Impossible de créer la clé d\'urgence : %s', e)
            return None

    # ── Chiffrement / déchiffrement ───────────────────────────────────────────
    def encrypt_for_user(self, plaintext: str) -> str:
        self.ensure_one()
        if not self.rsa_public_key:
            raise exceptions.UserError(
                f'L\'utilisateur {self.name} n\'a pas de clé de chiffrement. '
                'Veuillez initialiser le chiffrement dans vos préférences.'
            )
        pub_key = serialization.load_pem_public_key(
            self.rsa_public_key.encode('utf-8'),
            backend=default_backend(),
        )
        ciphertext = pub_key.encrypt(
            plaintext.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return base64.b64encode(ciphertext).decode('utf-8')

    def decrypt_with_password(self, ciphertext_b64: str, password: str) -> str:
        self.ensure_one()
        if not self.rsa_private_key_enc:
            raise exceptions.UserError('Aucune clé privée trouvée. Initialisez le chiffrement.')
        try:
            encrypted_private = base64.b64decode(self.rsa_private_key_enc)
            private_key = serialization.load_pem_private_key(
                encrypted_private,
                password=password.encode('utf-8'),
                backend=default_backend(),
            )
        except (ValueError, TypeError):
            raise ValueError('Mot de passe incorrect ou clé corrompue.')

        ciphertext = base64.b64decode(ciphertext_b64)
        plaintext = private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        return plaintext.decode('utf-8')

    def reencrypt_private_key(self, old_password: str, new_password: str):
        self.ensure_one()
        encrypted_private = base64.b64decode(self.rsa_private_key_enc)
        try:
            private_key = serialization.load_pem_private_key(
                encrypted_private,
                password=old_password.encode('utf-8'),
                backend=default_backend(),
            )
        except (ValueError, TypeError):
            raise ValueError('Ancien mot de passe incorrect.')

        new_encrypted = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                new_password.encode('utf-8')
            ),
        )
        vals = {
            'rsa_private_key_enc': base64.b64encode(new_encrypted).decode('utf-8'),
        }
        emergency_key_enc = self._build_emergency_key(new_encrypted)
        if emergency_key_enc:
            vals['emergency_key_enc'] = emergency_key_enc
        self.sudo().write(vals)
        _logger.info('[os_contact_encrypted] Clé privée re-chiffrée pour %s', self.login)

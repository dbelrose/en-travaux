from odoo import models, fields, api, exceptions
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
import base64
import logging

_logger = logging.getLogger(__name__)


class EmergencyExportWizard(models.TransientModel):
    """
    Mécanisme de récupération d'urgence en deux volets :

    Volet 1 — Configuration (admin) :
        L'administrateur génère sa propre paire RSA de récupération.
        Sa clé publique est stockée dans ir.config_parameter.
        La clé privée admin est exportée sous forme de fichier PEM chiffré
        à conserver hors-ligne (coffre-fort, gestionnaire de secrets).

    Volet 2 — Accès d'urgence (admin) :
        L'admin choisit un utilisateur.
        Il fournit sa clé privée admin (PEM, chiffrée par son MDP).
        Le système déchiffre la clé privée de l'utilisateur (emergency_key_enc)
        et affiche les données en clair ou les re-chiffre sous un nouveau MDP.
        Chaque accès est journalisé dans mail.message sur l'utilisateur concerné.
    """
    _name = 'os.emergency.export.wizard'
    _description = 'Récupération d\'urgence des clés de chiffrement'

    mode = fields.Selection([
        ('setup',   'Configuration initiale (admin)'),
        ('recover', 'Accès d\'urgence (admin)'),
    ], string='Mode', required=True, default='setup')

    state = fields.Selection([
        ('form',  'Formulaire'),
        ('done',  'Succès'),
        ('error', 'Erreur'),
    ], default='form')

    # ── Setup ────────────────────────────────────────────────────────────────
    admin_password           = fields.Char(string='Mot de passe admin (pour protéger la clé privée)')
    admin_password_confirm   = fields.Char(string='Confirmer')
    admin_private_key_export = fields.Binary(
        string='Clé privée admin (fichier PEM — à conserver hors-ligne)',
        readonly=True,
        attachment=False,
    )
    admin_private_key_filename = fields.Char(default='emergency_admin_private.pem')
    setup_done_info          = fields.Char(readonly=True)

    # ── Recover ──────────────────────────────────────────────────────────────
    target_user_id          = fields.Many2one(
        'res.users',
        string='Utilisateur à récupérer',
        domain=[('rsa_private_key_enc', '!=', False)],
    )
    admin_private_key_input = fields.Text(
        string='Clé privée admin (coller le contenu PEM)',
        help='Collez ici le contenu du fichier emergency_admin_private.pem',
    )
    admin_key_password      = fields.Char(
        string='Mot de passe de la clé privée admin',
        password=True,
    )
    new_user_password       = fields.Char(
        string='Nouveau mot de passe pour l\'utilisateur récupéré',
        password=True,
        help='La clé privée de l\'utilisateur sera re-chiffrée avec ce mot de passe.',
    )
    new_user_password_confirm = fields.Char(string='Confirmer')
    error_message           = fields.Char(readonly=True)
    recovery_info           = fields.Char(readonly=True)

    # ── Volet 1 : Configuration ──────────────────────────────────────────────
    def action_setup_emergency(self):
        """Génère la paire RSA admin et stocke la clé publique en paramètre système."""
        self.ensure_one()
        self._check_is_crypto_admin()

        if not self.admin_password:
            raise exceptions.UserError('Le mot de passe admin est obligatoire.')
        if self.admin_password != self.admin_password_confirm:
            raise exceptions.UserError('Les mots de passe ne correspondent pas.')

        # Générer la paire RSA admin
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,       # 4096 bits pour la clé maîtresse de récupération
            backend=default_backend(),
        )

        # Clé publique → paramètre système
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.env['ir.config_parameter'].sudo().set_param(
            'os_contact_encrypted.emergency_admin_public_key',
            public_pem.decode('utf-8'),
        )

        # Clé privée → fichier PEM chiffré, à télécharger et conserver hors-ligne
        encrypted_private = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                self.admin_password.encode('utf-8')
            ),
        )

        self.write({
            'state': 'done',
            'admin_private_key_export': base64.b64encode(encrypted_private),
            'setup_done_info': (
                'Clé publique admin enregistrée. '
                'Téléchargez la clé privée ci-dessous et conservez-la dans un endroit sécurisé '
                '(coffre-fort, gestionnaire de secrets hors-ligne). '
                'Sans ce fichier, la récupération d\'urgence sera impossible.'
            ),
        })

        # Regénérer les clés d'urgence pour tous les utilisateurs existants
        self._rebuild_all_emergency_keys()

        _logger.warning(
            '[os_contact_encrypted] Clé admin de récupération générée par %s (id=%s)',
            self.env.user.login, self.env.user.id,
        )

        # Retourner l'action pour maintenir le dialog ouvert (afficher le bouton téléchargement)
        return self._reopen_wizard()

    def _rebuild_all_emergency_keys(self):
        """
        Après une nouvelle clé admin, re-construit emergency_key_enc
        pour tous les utilisateurs. Nécessite que chaque utilisateur
        re-génère sa propre paire (on ne peut pas re-chiffrer sans leur MDP).
        On se contente de vider emergency_key_enc des anciens enregistrements.
        """
        users_with_keys = self.env['res.users'].sudo().search([
            ('rsa_private_key_enc', '!=', False),
        ])
        # On vide : ils devront lancer InitKeypair à leur prochaine connexion
        users_with_keys.sudo().write({'emergency_key_enc': False})
        _logger.info(
            '[os_contact_encrypted] emergency_key_enc vidé pour %d utilisateurs '
            '(nécessitent re-init)', len(users_with_keys)
        )

    # ── Volet 2 : Accès d'urgence ────────────────────────────────────────────
    def action_recover(self):
        """
        Déchiffre la clé privée d'un utilisateur via la clé admin,
        puis la re-chiffre avec un nouveau mot de passe utilisateur.
        Journalise l'accès.
        """
        self.ensure_one()
        self._check_is_crypto_admin()

        if not self.target_user_id:
            raise exceptions.UserError('Sélectionnez un utilisateur.')
        if not self.admin_private_key_input:
            raise exceptions.UserError('La clé privée admin est obligatoire.')
        if not self.admin_key_password:
            raise exceptions.UserError('Le mot de passe de la clé privée admin est obligatoire.')
        if not self.new_user_password:
            raise exceptions.UserError('Le nouveau mot de passe utilisateur est obligatoire.')
        if self.new_user_password != self.new_user_password_confirm:
            raise exceptions.UserError('Les nouveaux mots de passe ne correspondent pas.')

        target = self.target_user_id

        if not target.emergency_key_enc:
            self.write({
                'state': 'error',
                'error_message': (
                    f'L\'utilisateur {target.name} n\'a pas de clé d\'urgence. '
                    'Il doit re-initialiser son chiffrement.'
                ),
            })
            return

        # ── Charger la clé privée admin ──────────────────────────────────────
        try:
            admin_private_key = serialization.load_pem_private_key(
                self.admin_private_key_input.strip().encode('utf-8'),
                password=self.admin_key_password.encode('utf-8'),
                backend=default_backend(),
            )
        except Exception:
            self.write({
                'state': 'error',
                'error_message': 'Impossible de charger la clé privée admin. Vérifiez le fichier et le mot de passe.',
            })
            return self._reopen_wizard()

        # ── Déchiffrer la couche d'urgence → obtenir la clé privée utilisateur ──
        try:
            emergency_ciphertext = base64.b64decode(target.emergency_key_enc)
            user_private_key_pem = admin_private_key.decrypt(
                emergency_ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            # user_private_key_pem est le PEM chiffré avec l'ANCIEN MDP utilisateur
            # On doit le re-chiffrer avec le NOUVEAU MDP
            user_private_key = serialization.load_pem_private_key(
                user_private_key_pem,
                password=None,     # La couche urgence ne contient pas le MDP user
                backend=default_backend(),
            )
        except Exception:
            # Cas où user_private_key_pem est encore chiffré par l'ancien MDP user
            # (double chiffrement : MDP user + clé admin)
            # On re-chiffre directement avec le nouveau MDP sans déchiffrer la couche user
            try:
                new_encrypted = self._reencrypt_recovered_key(
                    user_private_key_pem, self.new_user_password
                )
            except Exception as e:
                self.write({
                    'state': 'error',
                    'error_message': f'Échec du déchiffrement de la clé d\'urgence : {e}',
                })
                return self._reopen_wizard()
        else:
            # Clé privée déchiffrée avec succès (non chiffrée par MDP user dans l'urgence)
            new_encrypted = user_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    self.new_user_password.encode('utf-8')
                ),
            )

        # ── Mettre à jour la clé privée + le MDP Odoo de l'utilisateur ──────
        target.sudo().write({
            'rsa_private_key_enc': base64.b64encode(new_encrypted).decode('utf-8'),
        })
        try:
            target.sudo()._change_password(self.new_user_password)
        except Exception as e:
            _logger.error('[os_contact_encrypted] Échec changement MDP lors récupération : %s', e)

        # ── Journal d'audit ──────────────────────────────────────────────────
        self._log_emergency_access(target)

        self.write({
            'state': 'done',
            'recovery_info': (
                f'Récupération réussie pour {target.name}. '
                f'Son mot de passe a été réinitialisé. '
                'Il pourra se connecter avec le nouveau mot de passe et accéder à ses données chiffrées.'
            ),
        })
        return self._reopen_wizard()

    def _reencrypt_recovered_key(self, encrypted_pem: bytes, new_password: str) -> bytes:
        """
        Dans le cas d'un double chiffrement (MDP user + admin),
        la couche urgence contient la clé privée chiffrée par le MDP user.
        On ne peut pas la déchiffrer sans le MDP user.
        On la remplace directement en la re-chiffrant avec le nouveau MDP.
        Note : cela implique de connaître la clé privée en clair à un moment donné.
        Ce cas ne devrait pas se produire avec l'architecture actuelle.
        """
        raise ValueError(
            'Double chiffrement détecté. Impossible de récupérer sans le mot de passe utilisateur original. '
            'Contactez le développeur du module.'
        )

    def _log_emergency_access(self, target_user):
        """Journalise l'accès d'urgence dans le chatter de l'utilisateur cible."""
        admin = self.env.user
        message = (
            f'🚨 Accès d\'urgence aux clés de chiffrement\n'
            f'Administrateur : {admin.name} ({admin.login})\n'
            f'Date : {fields.Datetime.now()}\n'
            f'Raison : Récupération via wizard d\'urgence os_contact_encrypted'
        )
        try:
            target_user.sudo().message_post(
                body=message,
                subject='Accès d\'urgence aux clés de chiffrement',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        except Exception as e:
            _logger.warning('[os_contact_encrypted] Impossible de journaliser l\'accès : %s', e)

        _logger.warning(
            '[os_contact_encrypted] ACCÈS URGENCE : admin=%s (id=%s) → user=%s (id=%s)',
            admin.login, admin.id, target_user.login, target_user.id,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _check_is_crypto_admin(self):
        if not self.env.user.has_group('os_contact_encrypted.group_crypto_admin'):
            raise exceptions.AccessError(
                'Seul l\'administrateur de chiffrement peut effectuer cette opération.'
            )

    def action_retry(self):
        self.write({
            'state': 'form',
            'admin_password': False,
            'admin_password_confirm': False,
            'admin_private_key_input': False,
            'admin_key_password': False,
            'new_user_password': False,
            'new_user_password_confirm': False,
            'error_message': False,
        })
        return self._reopen_wizard()

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

    def _reopen_wizard(self):
        """Retourne une action qui maintient le dialog ouvert sur cet enregistrement."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

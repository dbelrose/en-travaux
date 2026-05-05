from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)


class ChangePasswordWizard(models.TransientModel):
    _name = 'os.change.password.wizard'
    _description = 'Changement du mot de passe avec re-chiffrement de la clé privée'

    state = fields.Selection([
        ('form',  'Formulaire'),
        ('done',  'Succès'),
        ('error', 'Erreur'),
    ], default='form')

    old_password         = fields.Char(string='Mot de passe actuel')
    new_password         = fields.Char(string='Nouveau mot de passe')
    new_password_confirm = fields.Char(string='Confirmer le nouveau mot de passe')
    error_message        = fields.Char(readonly=True)

    def action_change(self):
        self.ensure_one()
        user = self.env.user

        # ── Validations ──────────────────────────────────────────────────────
        if not all([self.old_password, self.new_password, self.new_password_confirm]):
            raise exceptions.UserError('Tous les champs sont obligatoires.')
        if self.new_password != self.new_password_confirm:
            raise exceptions.UserError('Les nouveaux mots de passe ne correspondent pas.')
        if self.old_password == self.new_password:
            raise exceptions.UserError('Le nouveau mot de passe doit être différent de l\'ancien.')
        if len(self.new_password) < 8:
            raise exceptions.UserError('Le mot de passe doit comporter au moins 8 caractères.')

        # ── Authentification de l'ancien mot de passe ────────────────────────
        db = self.env.cr.dbname
        uid = self.env['res.users'].sudo().authenticate(db, user.login, self.old_password, {})
        if not uid:
            self.write({'state': 'error', 'error_message': 'Ancien mot de passe incorrect.'})
            return

        if not user.rsa_private_key_enc:
            raise exceptions.UserError(
                'Aucune clé de chiffrement trouvée. '
                'Initialisez d\'abord le chiffrement dans vos préférences.'
            )

        # ── Re-chiffrement de la clé privée ─────────────────────────────────
        try:
            user.reencrypt_private_key(self.old_password, self.new_password)
        except ValueError as e:
            self.write({'state': 'error', 'error_message': str(e)})
            return
        except Exception as e:
            _logger.error('[os_contact_encrypted] Erreur re-chiffrement clé : %s', e)
            self.write({'state': 'error', 'error_message': f'Erreur inattendue : {e}'})
            return

        # ── Changement du mot de passe Odoo ─────────────────────────────────
        try:
            user.sudo()._change_password(self.new_password)
        except Exception as e:
            _logger.error('[os_contact_encrypted] Erreur changement MDP Odoo : %s', e)
            # La clé a déjà été re-chiffrée — on doit signaler l'incohérence
            self.write({
                'state': 'error',
                'error_message': (
                    'La clé de chiffrement a été mise à jour mais le changement '
                    f'du mot de passe Odoo a échoué : {e}. Contactez votre administrateur.'
                ),
            })
            return

        _logger.info(
            '[os_contact_encrypted] Mot de passe + clé re-chiffrée pour %s (id=%s)',
            user.login, user.id,
        )
        return self.write({'state': 'done'})

    def action_retry(self):
        return self.write({
            'state': 'form',
            'old_password': False,
            'new_password': False,
            'new_password_confirm': False,
            'error_message': False,
        })

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

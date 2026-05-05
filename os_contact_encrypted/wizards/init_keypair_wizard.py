from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)


class InitKeypairWizard(models.TransientModel):
    _name = 'os.init.keypair.wizard'
    _description = 'Initialisation des clés de chiffrement RSA'

    state = fields.Selection([
        ('form',    'Formulaire'),
        ('done',    'Succès'),
        ('already', 'Déjà initialisé'),
        ('error',   'Erreur'),
    ], default='form')

    password         = fields.Char(string='Votre mot de passe Odoo')
    password_confirm = fields.Char(string='Confirmer le mot de passe')
    force_regenerate = fields.Boolean(
        string='Régénérer les clés (attention : les données existantes deviendront illisibles)',
        default=False,
    )
    has_keys      = fields.Boolean(compute='_compute_has_keys')
    warning_regen = fields.Char(compute='_compute_warning')
    error_message = fields.Char(readonly=True)

    @api.depends()
    def _compute_has_keys(self):
        for rec in self:
            rec.has_keys = bool(self.env.user.rsa_public_key)

    @api.depends('has_keys', 'force_regenerate')
    def _compute_warning(self):
        for rec in self:
            if rec.has_keys and rec.force_regenerate:
                rec.warning_regen = (
                    'ATTENTION : Régénérer les clés rendra illisibles TOUS les champs '
                    'chiffrés de vos contacts existants. Cette action est irréversible.'
                )
            else:
                rec.warning_regen = False

    def action_generate(self):
        self.ensure_one()
        user = self.env.user

        if not self.password:
            raise exceptions.UserError('Le mot de passe est obligatoire.')
        if self.password != self.password_confirm:
            raise exceptions.UserError('Les mots de passe ne correspondent pas.')

        # Authentification Odoo pour valider le mot de passe
        db = self.env.cr.dbname
        uid = self.env['res.users'].sudo().authenticate(db, user.login, self.password, {})
        if not uid:
            self.write({'state': 'error', 'error_message': 'Mot de passe Odoo incorrect.'})
            return {'type': 'ir.actions.act_window_close'} if False else None

        if user.rsa_public_key and not self.force_regenerate:
            return self.write({'state': 'already'})

        try:
            user.generate_rsa_keypair(self.password)
            _logger.info(
                '[os_contact_encrypted] InitKeypair réussi pour %s (id=%s)',
                user.login, user.id
            )
        except Exception as e:
            _logger.error('[os_contact_encrypted] Erreur InitKeypair : %s', e)
            self.write({'state': 'error', 'error_message': str(e)})
            return

        return self.write({'state': 'done'})

    def action_retry(self):
        return self.write({
            'state': 'form',
            'password': False,
            'password_confirm': False,
            'error_message': False,
        })

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}

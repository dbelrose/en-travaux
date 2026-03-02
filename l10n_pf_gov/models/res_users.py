from odoo import models, api, fields, _
from datetime import datetime, timedelta


class ResUsers(models.Model):
    _inherit = 'res.users'

    def reset_password(self, login):
        """ retrieve the user corresponding to login (login or email),
            and reset their password
        """
        users = self.search([('login', '=', login)])
        # Vulnérabilité 2 – Importante – Énumération des comptes utilisateurs possible
        # Recommandation 3 – Uniformiser les messages du formulaire de mot de passe oublié
        # WSTG-IDNT-04 (Testing for Account Enumeration
        # and Guessable User Account)
        if not users:
            # users = self.search([('email', '=', login)])
            raise Exception(_('An email has been sent with credentials to reset your password'))
        if len(users) != 1:
            # raise Exception(_('Reset password: invalid username or email'))
            raise Exception(_('An email has been sent with credentials to reset your password'))
        return users.action_reset_password()

    @api.model
    def archive_inactive_users(self):
        # Obtenir l'utilisateur administrateur
        admin_user = self.env.ref('base.user_admin')

        # Récupérer le délai d'inactivité depuis les paramètres
        inactivity_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'l10n_pf_gov.inactivity_days', default=120))
        limit_date = datetime.now() - timedelta(days=inactivity_days)

        # Obtenir les modèles d'email
        template_alert = self.env.ref('l10n_pf_gov.email_template_alert_inactive_users')
        template_archive = self.env.ref('l10n_pf_gov.email_template_archive_inactive_users')

        # Rechercher les utilisateurs inactifs
        inactive_users = self.search([('login_date', '<', limit_date),
        # https://gov-pf.atlassian.net/jira/software/projects/ODO/boards/15?selectedIssue=ODO-88
                                      ('active', '==', True),
        # End
                                      ('id', '!=', admin_user.id)])

        # Envoyer des alertes par email avant la désactivation
        alert_intervals = [30, 15, 5]
        for days_before in alert_intervals:
            alert_date = limit_date + timedelta(days=days_before)

            # https://gov-pf.atlassian.net/jira/software/projects/ODO/boards/15?selectedIssue=ODO-88
            users_to_alert = self.search([('login_date', '==', alert_date),
                                          ('active', '==', True),
            # users_to_alert = self.search([('login_date', '<', alert_date),
            #                               ('login_date', '>=', limit_date - timedelta(days=days_before)),
            # End
                                          ('id', '!=', admin_user.id)])
            for user in users_to_alert:
                template_alert.with_context(
                    inactivity_days=inactivity_days,
                    days_before=days_before,
                    login_url='https://your-odoo-instance.com/web/login'
                ).send_mail(user.id, force_send=True)

        # Archiver les utilisateurs inactifs et envoyer un email de notification
        for user in inactive_users:
            user.active = False
            template_archive.with_context(inactivity_days=inactivity_days).send_mail(user.id, force_send=True)
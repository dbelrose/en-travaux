from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # alias_domain = fields.Char(
    #     default='smtp.gov.pf',
    # )
    auth_signup_reset_password = fields.Boolean(
        default=False,
    )
    external_email_server_default = fields.Boolean(
        help="Serveur de messagerie par défaut",
        default=True,
    )
    module_partner_autocomplete = fields.Boolean(
        default=False,
    )
    user_default_rights = fields.Boolean(
        default=True,
    )
    inactivity_days = fields.Integer(
        string="Archivage si inactif depuis (jours)",
        default=60,
        config_parameter='l10n_pf_gov.inactivity_days')

    @api.model
    def set_values(self):

        super(ResConfigSettings, self).set_values()

        self.env['ir.config_parameter'].sudo().set_param('auth_signup.reset_password', False)

        self.env['ir.config_parameter'].sudo().set_param('base_setup.default_user_rights', True)
        self.env['ir.config_parameter'].sudo().set_param('base_setup.external_email_server_default', True)

        # self.env['ir.config_parameter'].sudo().set_param('mail.alias.alias_domain', 'smtp.gov.pf')

# class Module(models.Model)
#     _inherit = 'ir.module.module'
#
#     @api.model
#     def set_values(self):
        module = self.env['ir.module.module'].search([('name', '=', 'partner_autocomplete')])
        if module.state == 'installed':
            module.module_uninstall()

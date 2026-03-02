# -*- coding: utf-8 -*-

from odoo import models, fields, api


# Entreprises
class ResPartner(models.Model):
    _inherit = 'res.partner'

    initials = fields.Char(string='Sigle')
    fax = fields.Char(string='Fax')
    pobox = fields.Char(string='Boîte postale')
    first_name = fields.Char(string='Prénom')
    last_name = fields.Char(string='Nom de famille')
    full_name = fields.Char(string='Nom complet')

    @api.onchange('first_name', 'last_name')
    def compute_name(self):
        if self.last_name and self.first_name:
            self.name = self.last_name + " " + self.first_name
        elif self.first_name:
            self.name = self.first_name
        elif self.last_name:
            self.name = self.last_name

    def set_email(self):
        users = self.env['res.users'].search([('active', '=', True)])
        for user in users:
            if self.id == user.partner_id and self.acttive and self.email is None and not self.is_company:
                self.email = user.login

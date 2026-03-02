# -*- coding: utf-8 -*-

from odoo import models, fields

# Entreprises
class Company(models.Model):
	_inherit = 'res.company'
	report_header = fields.Html(string='Entête')
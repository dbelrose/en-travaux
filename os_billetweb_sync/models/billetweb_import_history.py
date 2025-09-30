from odoo import models, fields

class BilletWebImportHistory(models.Model):
    _name = 'billetweb.import.history'
    _description = 'Historique des imports BilletWeb'
    _order = 'date_import desc'

    date_import = fields.Datetime(string="Date d'import", default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string="Société")
    number_of_payouts = fields.Integer(string="Nombre de virements")
    number_of_errors = fields.Integer(string="Nombre d'erreurs")
    status = fields.Selection([
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur')
    ], string="Statut", default='success')
    log_message = fields.Text(string="Détails")

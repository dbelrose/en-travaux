from odoo import models, fields, api


class BilletwebEventStats(models.Model):
    _name = 'billetweb.event.stats'
    _description = 'Statistiques des événements BilletWeb'
    _order = 'event_date desc'

    name = fields.Char(string="Nom de l'événement")
    event_id = fields.Char(string="ID événement BilletWeb")
    event_date = fields.Datetime(string="Date de l'événement")
    company_id = fields.Many2one('res.company', string="Société")

    number_of_tickets = fields.Integer(string="Nombre de billets vendus", default=0)
    number_of_refunds = fields.Integer(string="Nombre de remboursements", default=0)
    amount_total = fields.Monetary(string="Montant total brut", currency_field='currency_id')
    amount_refunded = fields.Monetary(string="Montant remboursé", currency_field='currency_id')
    amount_net = fields.Monetary(string="Montant net encaissé", currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', string="Devise", default=lambda self: self.env.ref('base.EUR'))

    @api.depends('amount_total', 'amount_refunded')
    def _compute_amount_net(self):
        for record in self:
            record.amount_net = record.amount_total - record.amount_refunded

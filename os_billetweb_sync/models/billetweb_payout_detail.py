from odoo import models, fields


class BilletWebPayoutDetail(models.Model):
    _name = 'billetweb.payout.detail'
    _description = "Détail des ventes BilletWeb"

    payout_id = fields.Many2one('billetweb.payout', string="Virement BilletWeb", required=True)
    ext_id = fields.Char(string="Identifiant externe")
    order_id = fields.Char(string="Commande")
    date = fields.Datetime(string="Date de vente")
    price = fields.Monetary(string="Montant TTC", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string="Devise", default=lambda self: self.env.ref('base.EUR'))
    tax_rate = fields.Float(string="Taux de TVA")
    tax_amount = fields.Monetary(string="Montant TVA", currency_field='currency_id')
    fees = fields.Monetary(string="Frais BilletWeb", currency_field='currency_id')
    event = fields.Char(string="Événement")
    commission_invoice_id = fields.Many2one('account.move', string="Facture de commission")

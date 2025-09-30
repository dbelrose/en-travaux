from odoo import models, fields


class BilletwebPayout(models.Model):
    _name = 'billetweb.payout'
    _description = 'Virement BilletWeb importé'
    _rec_name = 'payout_id'
    _order = 'date desc'

    company_id = fields.Many2one('res.company', string="Société", required=True, default=lambda self: self.env.company)
    payout_id = fields.Char(string="ID BilletWeb", required=True, index=True)
    date = fields.Date(string="Date du virement")
    amount = fields.Monetary(string="Montant", currency_field='currency_id')
    partner_id = fields.Many2one('res.partner', string="Bénéficiaire")
    bank_account_id = fields.Many2one('res.partner.bank', string="Compte IBAN")
    account = fields.Char(string="Account")
    iban = fields.Char(string="IBAN")
    swift = fields.Char(string="BIC")
    imported_payment_id = fields.Many2one('account.payment', string="Paiement Odoo lié")
    currency_id = fields.Many2one('res.currency', string="Devise", default=lambda self: self.env.ref('base.EUR'))
    payout_detail_ids = fields.One2many('billetweb.payout.detail', 'payout_id', string="Détails des paiements")
    invoice_ids = fields.One2many('account.move', 'billetweb_payout_id', string="Factures de commission")

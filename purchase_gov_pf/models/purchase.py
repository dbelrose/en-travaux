# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _inherit = 'purchase.order.line'

    # https://www.tauturu.gov.pf/front/ticket.form.php?id=137339
    duplicate_line = fields.Boolean(string="Dupliquer cette ligne")
    # End

    account_budget_id = fields.Many2one(
        'account.account', string='Budgeted Account',
        index=True, ondelete="cascade",
        domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False)]",
        check_company=True)
    pack_qty = fields.Float(
        string='Pack Qty',
        digits='Pack Unit of Measure',
        required=True,
        default=1.0)

    def _get_computed_account(self):
        self.ensure_one()
        self = self.with_company(self.order_id.company_id)

        if not self.product_id:
            return

        fiscal_position = self.order_id.fiscal_position_id
        accounts = self.product_id.product_tmpl_id.get_product_accounts(fiscal_pos=fiscal_position)
        return accounts['expense'] or self.account_budget_id

    def _product_id_change(self):
        super(PurchaseOrderLine, self)._product_id_change()
        self.account_budget_id = self._get_computed_account()

    def _prepare_account_move_line(self, move=False):
        res = super(PurchaseOrderLine, self)._prepare_account_move_line(move=move)
        account = self.account_budget_id
        if account:
            res.update({
                'account_budget_id': account,
            })
        return res


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    VALEURANEPASDEPASSER=2

    ref = fields.Char('Ref', copy=False)
    department_id = fields.Many2one(comodel_name='hr.department', string='Department', help='This is the Department the purchase order is for')
    account_budget_id = fields.Many2one(
        'account.account', string='Budgeted Account',
        compute='_compute_budget_account',
        inverse='_inverse_budget_account',
        index=True, ondelete="cascade",
        domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False)]",
        check_company=True,
        tracking=True)
    requisition_id = fields.Many2one(required=True)
    invest = fields.Selection(
        selection=[
            ('invest', 'Investissement'),
            ('fonction', 'Fonctionnement'),
        ],
        default='invest',
        string='Investissement/Fonctionnement')
    transport_ref = fields.Char(
        string='Transport ref.',
        help='Saisir le numéro de référence du vol ou du bateau.')
    departure_place = fields.Char(
        string='Lieu de départ',
        help="Saisir le lieu de départ.")
    arrival_place = fields.Char(
        string="Lieux visités",
        help="Saisir les lieux visités.")
    company_currency_id = fields.Many2one(
        string='Company Currency',
        readonly=True,
        related='company_id.currency_id')

    # Regular's purchase order type specific fields
    tva_5 = fields.Monetary(
        string='TVA 5%', currency_field='company_currency_id')
    tva_13 = fields.Monetary(
        string='TVA 13%', currency_field='company_currency_id')
    tva_16 = fields.Monetary(
        string='TVA 16%', currency_field='company_currency_id')
    tva_social = fields.Monetary(
        string='TVA SOCIAL', currency_field='company_currency_id')
    total_engaged = fields.Monetary(
        string='Total engagé', store=True, compute='_compute_total_engaged')
    is_import = fields.Boolean(
        string='Is tva import', default=False, store=True, compute='_compute_is_import')
    #Calcul des différents taux de taxe
    tax_only = fields.Monetary(default=0, compute='_compute_tax', string="TAX", currency_field='company_currency_id')
    cps_only = fields.Monetary(default=0, compute='_compute_tax', string="CPS 1%", currency_field='company_currency_id')

    # Requisition's purchase order type specific fields
    option_date = fields.Date(
        string="Date d'option",
        help="Saisir la date d'option du vol si existante.")
    passenger_ids = fields.Many2many(
        comodel_name='hr.employee',
        string='Passager(s)',
        help='Choisir le(s) passager(s)')
    departure_date = fields.Date(string='Date de départ')
    return_date = fields.Date(string='Date de retour')
    expense_sheet_ids = fields.Many2many(
        comodel_name='hr.expense.sheet',
        string='Expense sheet')

    # Freight's purchase order type specific fields
    partner_shipping_id = fields.Many2one(
        comodel_name='res.partner',
        string='Délivré à',
        help='Saisir la personne ou entreprise recevant le(s) colis')

    @api.onchange('requisition_id')
    def _onchange_requisition_id(self):
        super(PurchaseOrder, self)._onchange_requisition_id()
        self.department_id = self.requisition_id.department_id.id or False
        self.invest = self.requisition_id.invest

    @api.onchange('departure_date', 'return_date')
    def _onchange_travel_date(self):
        if (self.departure_date and self.return_date
                and self.departure_date > self.return_date):
            raise ValidationError(
                _('The departure date must be earlier than the return date.'))

    @api.onchange('expense_sheet_ids')
    def onchange_check_expense_sheets(self):
        res = {}
        is_expense_sheets_error = self._check_expense_sheet()
        if is_expense_sheets_error:
            res['warning'] = {
                'title': _('Attention !'),
                'message': _('Les notes de frais sélectionnées présentent des différences :\n - ' + is_expense_sheets_error)
            }
        return res

    def _check_expense_sheet(self):
        expense_type = None
        for sheet in self.expense_sheet_ids:
            if expense_type is None:
                expense_type = sheet.expense_type
                account_budget = sheet.transport_account_budget
            elif sheet.expense_type == 'meal_allowance':
                return 'Mauvais type de dépense : panier'
            elif sheet.expense_type != expense_type:
                return 'Types de dépense différents'
            elif sheet.transport_account_budget != account_budget:
                return 'Articles différents '
        return False

    @api.depends("order_line.account_budget_id")
    def _compute_budget_account(self):
        for rec in self:
            account = rec.mapped("order_line.account_budget_id")
            if len(account) == 1:
                rec.account_budget_id = account.id
            else:
                rec.account_budget_id = False

    def _inverse_budget_account(self):
        for rec in self:
            if rec.account_budget_id:
                for line in rec.order_line:
                    line.account_budget_id = rec.account_budget_id

    @api.depends('amount_total', 'tva_5', 'tva_13', 'tva_16', 'tva_social')
    def _compute_total_engaged(self):
        for order in self:
            converted_amount = order.currency_id._convert(
                order.amount_total, order.company_currency_id, order.company_id, order.date_approve or fields.Date.context_today(order))
            order.total_engaged = converted_amount + \
                                  order.tva_5 + order.tva_13 + order.tva_16 +order.tva_social

    @api.depends('order_type', 'order_line.taxes_id')
    def _compute_is_import(self):
        for order in self:
            if order.order_type == self.env.ref('purchase_order_type.po_type_regular'):
                order.is_import = False
                for line in order.order_line:
                    if self.env.ref("%s.%d_%s" % ('l10n_pf_public', self.company_id.id, 'tva_import_0')) in line.taxes_id:
                        order.is_import = True
                        break

    @api.depends(
        'order_type',
        'order_line.taxes_id',
        'order_line.price_subtotal',
        'order_line.price_total'
    )
    def _amount_all(self):
        for order in self:
            amount_untaxed = 0.0
            for line in order.order_line:
                line._compute_amount()
                amount_untaxed += line.price_subtotal

            currency = order.currency_id or order.partner_id.property_purchase_currency_id or self.env.company.currency_id

            # Si la devise de la commande est XPF → on additionne les TVA XPF
            if currency == order.company_currency_id:
                amount_other = order.tva_5 + order.tva_13 + order.tva_16
                amount_cps = order.cps_only
                order.update({
                    'amount_untaxed': currency.round(amount_untaxed),
                    'amount_tax': currency.round(amount_other) + currency.round(amount_cps),
                    'amount_total': amount_untaxed + amount_other + amount_cps,
                })
            else:
                # Sinon → logique standard (pas de TVA XPF dans le total)
                order.update({
                    'amount_untaxed': currency.round(amount_untaxed),
                    'amount_tax': 0.0,
                    'amount_total': amount_untaxed,
                })

    @api.onchange('tva_5', 'tva_13', 'tva_16', 'tva_social')
    def _onchange_tax(self):
        for record in self:
            if not record.is_import:
                if record.currency_id == record.company_currency_id:
                    record.tax_only = record.tva_5 + record.tva_13 + record.tva_16
                    record.amount_total = record.amount_untaxed + record.tax_only + record.cps_only
                else:
                    # En devise étrangère : on ne touche pas à amount_total ni à tax_only
                    record.tax_only = 0
                    record.amount_total = record.amount_untaxed

    @api.depends(
        'order_type',
        'order_line.taxes_id',
        'order_line.price_subtotal',
        'order_line.price_total'
    )
    def _compute_tax(self):
        for record in self:
            # Si la devise de la commande n'est pas XPF (devise société)
            if record.currency_id != record.company_currency_id:
                record.tax_only = 0
                record.cps_only = 0
                # On ne touche pas aux tva_* existantes
                continue

            # --- logique actuelle si devise = XPF ---
            sum_cps = sum_5 = sum_13 = sum_16 = sum_other = 0
            for rec in record.order_line:
                if rec.taxes_id:
                    for tax in rec.taxes_id:
                        if tax.name == "Contribution sociale":
                            sum_cps += rec.price_subtotal * tax.amount / 100
                        elif tax.name == "TVA déductible (achat) 5,0%":
                            sum_5 += rec.price_subtotal * tax.amount / 100
                        elif tax.name == "TVA déductible (achat) 13,0%":
                            sum_13 += rec.price_subtotal * tax.amount / 100
                        elif tax.name == "TVA déductible (achat) 16,0%":
                            sum_16 += rec.price_subtotal * tax.amount / 100
                        else:
                            sum_other += rec.price_subtotal * tax.amount / 100

            # affectations seulement si XPF
            if not record.is_import:
                if abs(record.tva_5 - sum_5) >= self.VALEURANEPASDEPASSER:
                    record.tva_5 = sum_5
                if abs(record.tva_13 - sum_13) >= self.VALEURANEPASDEPASSER:
                    record.tva_13 = sum_13
                if abs(record.tva_16 - sum_16) >= self.VALEURANEPASDEPASSER:
                    record.tva_16 = sum_16
                if abs(record.tva_social - sum_cps) >= self.VALEURANEPASDEPASSER:
                    record.tva_social = sum_cps
                record.tax_only = record.tva_5 + record.tva_13 + record.tva_16
                record.cps_only = record.tva_social
                record.amount_total = record.tax_only + record.cps_only + record.amount_untaxed
            else:
                record.tax_only = sum_5 + sum_13 + sum_16
                record.cps_only = sum_cps

    def button_confirm(self):
        for order in self:
            if order.state not in ['draft', 'sent']:
                continue
            # check homogeneity of expense type ids for po requisition
            if order.order_type == self.env.ref('purchase_gov_pf.po_type_requisition'):
                is_expense_sheets_error = order._check_expense_sheet()
                if is_expense_sheets_error:
                    raise ValidationError(
                        _('Attention, des différences importantes sont présentes entre vos notes de frais :\n - ' + is_expense_sheets_error))
            order._add_supplier_to_product()
            # We always want double validation
            order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        res = super(PurchaseOrder, self).button_confirm()
        return res

    def button_print_report(self):
        self.ensure_one()
        return self.env.ref('purchase_gov_pf.report_purchase_order').report_action(self)

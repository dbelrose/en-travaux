# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    def _get_my_department(self):
        employees = self.env.user.employee_ids
        return (employees[0].department_id if employees
                else self.env['hr.department'] or False)

    department_id = fields.Many2one(
        comodel_name='hr.department', string='Department',
        default=_get_my_department,
        help='Select the Department the purchase requisition is for')
    account_analytic_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        compute='_compute_analytic_account',
        inverse='_inverse_analytic_account',
        domain=[('is_project', '=', True)],
        help='This account will be propagated to all lines, if you need '
        'to use different accounts, define the account at line level.',
    )
    analytic_tag_ids = fields.Many2many(
        'account.analytic.tag', string='Analytic Tags',
        inverse='_inverse_analytic_tags',
        help='This account will be propagated to all lines, if you need '
        'to use different accounts, define the account at line level.',
    )
    invest = fields.Selection(
        selection=[
            ('invest', 'Investissement'),
            ('fonction', 'Fonctionnement'),
        ],
        default='invest',
        string='Investissement/Fonctionnement')
    parent_id = fields.Many2one(
        'purchase.requisition',
        string='Parent reference',
        index=True)
    child_ids = fields.One2many(
        'purchase.requisition', 'parent_id',
        string="Sub-requisitions",
        context={'active_test': False})
    hr_expense_sheet_ids = fields.One2many(
        'hr.expense.sheet', 'requisition_id', string="Hr Expense Sheet's list", copy=False)
    child_count = fields.Integer(
        compute='_compute_child_number', string='Number of childs')
    hr_expense_sheet_count = fields.Integer(
        compute='_compute_hr_expense_sheet_count', string='Count of hr expense sheet')
    amount_budget = fields.Monetary(
        string='Budget amount',
        help='Saisissez le montant en négatif s\'il s\'agit d\'une réduction')
    total_budget = fields.Monetary(
        string='Total Budget',
        store=True,
        compute='_compute_total_amount')
    amount_total = fields.Monetary(
        string='Total amount of purchase orders',
        store=True,
        compute='_compute_total_amount')
    # https://www.tauturu.gov.pf/front/ticket.form.php?id=137342
    article = fields.Char('Article budgétaire')
    # account_budget_id = fields.Many2one(
    #     'account.account', string='Budgeted Account',
    #     compute='_compute_budget_account',
    #     inverse='_inverse_budget_account',
    #     index=True, ondelete="cascade",
    #     domain="[('deprecated', '=', False), ('company_id', '=', 'company_id'),('is_off_balance', '=', False)]",
    #     check_company=True,
    #     tracking=True)
    # article = fields.Char('Article budgétaire', compute='_compute_article', store=True)
    # End
    code_visa = fields.Char('Numéro de visa', copy=False, help='Saisissez le numéro de Visa du CDE suivi de la date du Visa (ex : CDE/2938 du 12/11/2021)')
    approve_date = fields.Date('Date approve', readonly=True, copy=True)

    # https://www.tauturu.gov.pf/front/ticket.form.php?id=137342
    # @api.depends('account_budget_id.name')
    # def _compute_article(self):
    #     for record in self:
    #         record.article = record.account_budget_id.name if record.account_budget_id else ''
    # End

    @api.onchange('user_id')
    def onchange_user_id(self):
        employees = self.user_id.employee_ids
        self.department_id = (employees[0].department_id if employees
                              else self.env['hr.department'] or False)

    @api.depends('child_ids')
    def _compute_child_number(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    @api.depends('hr_expense_sheet_ids')
    def _compute_hr_expense_sheet_count(self):
        for rec in self:
            rec.hr_expense_sheet_count = len(rec.hr_expense_sheet_ids)

    @api.depends("line_ids.account_analytic_id")
    def _compute_analytic_account(self):
        for rec in self:
            account = rec.mapped("line_ids.account_analytic_id")
            if len(account) == 1:
                rec.account_analytic_id = account.id
            else:
                rec.account_analytic_id = False

    @api.depends('purchase_ids.state', 'purchase_ids.amount_total', 'child_ids.amount_total', 'hr_expense_sheet_ids.total_amount')
    def _compute_total_amount(self):
        for rec in self:
            amount_total = 0.0
            total_budget = rec.amount_budget
            for po in rec.purchase_ids.filtered(lambda purchase_order: purchase_order.state not in ['draft', 'cancel']):
                amount_total += po.amount_total
            # Child's amount
            if rec.child_ids:
                for child in rec.child_ids:
                    amount_total += child.amount_total
                    total_budget += child.amount_budget
            # Hr expense sheet's amount
            if rec.child_ids:
                for expense_sheet in rec.hr_expense_sheet_ids:
                    amount_total += expense_sheet.total_amount

            rec.amount_total = amount_total
            rec.total_budget = total_budget

    def _inverse_analytic_account(self):
        for rec in self:
            if rec.account_analytic_id:
                for line in rec.line_ids:
                    line.account_analytic_id = rec.account_analytic_id

    def _inverse_analytic_tags(self):
        for rec in self:
            if rec.analytic_tag_ids:
                for line in rec.line_ids:
                    line.analytic_tag_ids = rec.analytic_tag_ids

    def action_in_progress(self):
        self.ensure_one()
        # Here we have to get the inherited function because we need all the checks before assigning ir.sequence
        if not self.line_ids:
            raise UserError(_("You cannot confirm agreement '%s' because there is no product line.", self.name))
        if self.type_id.quantity_copy == 'none' and self.vendor_id:
            for requisition_line in self.line_ids:
                if requisition_line.price_unit <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without price.'))
                if requisition_line.product_qty <= 0.0:
                    raise UserError(_('You cannot confirm the blanket order without quantity.'))
                requisition_line.create_supplier_info()
            self.write({'state': 'ongoing'})
        else:
            self.write({'state': 'in_progress'})
        # Set the sequence number regarding the requisition type
        if self.name == 'New' and self.type_id == self.env.ref('purchase_gov_pf.type_epac'):
            seq_date = fields.Date.context_today(self)
            self.name = self.env['ir.sequence'].next_by_code('purchase.requisition.epac', sequence_date=seq_date)
            self.approve_date = fields.Date.context_today(self)
        res = super(PurchaseRequisition, self).action_in_progress()
        return res

    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})

    def action_open(self):
        if not self.user_has_groups('purchase.group_purchase_manager'):
            raise ValidationError(
                _('You are not allowed to validate a purchase requisition'))
        res = super(PurchaseRequisition, self).action_open()
        return res

    def action_done(self):
        if not self.user_has_groups('purchase.group_purchase_manager'):
            raise ValidationError(
                _('You are not allowed to close a purchase requisition'))
        res = super(PurchaseRequisition, self).action_done()
        return res


class PurchaseRequisitionLine(models.Model):
    _inherit = 'purchase.requisition.line'

    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        domain=[('is_project', '=', True)],
        string='Analytic Account')

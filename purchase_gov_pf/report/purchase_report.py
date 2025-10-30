# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, tools


class PurchaseOrderReport(models.AbstractModel):
    _name = 'report.purchase_gov_pf.gov_pf_purchase_order'
    _description = 'Special Purchase Reports for French Polynesia Government'

    def _get_highest_parent(self, partner):
        if partner.parent_id:
            return self._get_highest_parent(partner.parent_id)
        else:
            return partner

    def _get_highest_company(self, company):
        if company.parent_id:
            return self._get_highest_company(company.parent_id)
        else:
            return company

    def _get_report_values(self, docids, data=None):
        docs = self.env['purchase.order'].browse(docids)
        is_overseas = (docs.expense_sheet_ids and docs.expense_sheet_ids[0].expense_type == 'overseas' and
                       docs.order_type == self.env.ref('purchase_gov_pf.po_type_requisition')) or False
        if is_overseas:
            company_id = self._get_highest_company(docs.company_id)
        else:
            company_id = docs.company_id
        # get employee with no parent_id of company or parent company if exists
        no_parent_partner = self.env['hr.employee'].sudo().search([
            ('parent_id', '=', False),
            ('company_id', '=', docs.company_id.parent_id and docs.company_id.parent_id.id or docs.company_id.id)
        ])
        data = {
            'docs': docs,
            'no_parent_partner': no_parent_partner[0],
            'is_overseas': is_overseas,
            'company': company_id
        }

        if (docs.order_type in (
            self.env.ref('purchase_order_type.po_type_regular'),
            self.env.ref('purchase_gov_pf.po_type_requisition'),
            self.env.ref('l10n_pf_purchase_freight.po_type_freight')
        ) and docs.requisition_id.type_id in (
                self.env.ref('purchase_gov_pf.type_epac'),
                self.env.ref('purchase_gov_pf.type_marche')
        )):
            epac_initial_id = self._get_highest_parent(docs.requisition_id)
            data['initial_code_visa'] = epac_initial_id.code_visa
        return data


class PurchaseRequisitionReport(models.AbstractModel):
    _name = 'report.purchase_gov_pf.gov_pf_purchase_requisition_epac'
    _description = 'Special Purchase Requisition Reports for French Polynesia Government'

    def _get_highest_parent(self, partner):
        if partner.parent_id:
            return self._get_highest_parent(partner.parent_id)
        else:
            return partner

    def _get_report_values(self, docids, data=None):
        # get the records selected for this rendering of the report
        docs = self.env['purchase.requisition'].browse(docids)
        epac_initial_id = self._get_highest_parent(docs[0])
        epac_childs = self.env['purchase.requisition'].search([
            ('id', 'child_of', epac_initial_id.id),
            ('state', 'not in', ['draft'])
        ], order='create_date asc')
        counter = 0
        for i, child in enumerate(epac_childs):
            if (child == docs):
                counter = i
                break
        # get employee with no parent_id of company or parent company if exists
        no_parent_partner = self.env['hr.employee'].sudo().search([
            ('parent_id', '=', False),
            ('company_id', '=', docs.company_id.parent_id and docs.company_id.parent_id.id or docs.company_id.id)
        ])
        return {
            'docs': docs,
            'epac_counter': counter,
            'initial_code_visa': epac_initial_id.code_visa,
            'no_parent_partner': no_parent_partner[0]
        }

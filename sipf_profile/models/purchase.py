# Copyright 2022 INVITU (www.invitu.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def button_print_report(self):
        self.ensure_one()
        res = super(PurchaseOrder, self).button_print_report()
        if self.env.company == self.env.ref('base.main_company'):
            if not self.ref and self.state in ('purchase', 'done'):
                seq_date = fields.Date.context_today(self)
                # We have a special sequence for Freight
                if self.order_type == self.env.ref('l10n_pf_purchase_freight.po_type_freight'):
                    self.ref = (
                        self.env['ir.sequence']
                        .next_by_code('purchase.order.sipf.et', sequence_date=seq_date)
                    )
                if self.order_type == self.env.ref('purchase_gov_pf.po_type_requisition'):
                    self.ref = (
                        self.env['ir.sequence']
                        .next_by_code('purchase.order.sipf.req', sequence_date=seq_date)
                    )
                # We want a specific chrono for purchase orders in a MAPA or MAFOR
                if self.requisition_id.type_id in (
                        self.env.ref('purchase_gov_pf.type_mapa'),
                        self.env.ref('purchase_gov_pf.type_mafor')
                ) and self.order_type == self.env.ref('purchase_order_type.po_type_regular'):
                    self.ref = (
                        self.env['ir.sequence']
                        .next_by_code('purchase.order.sipf.ma', sequence_date=seq_date)
                    )
                # For other types, we have a sequence for each department
                if self.requisition_id.type_id not in (
                        self.env.ref('purchase_gov_pf.type_mapa'),
                        self.env.ref('purchase_gov_pf.type_mafor')
                ) and self.order_type == self.env.ref('purchase_order_type.po_type_regular'):
                    if self.department_id:
                        ref_sequence_list = {
                            'sipf_profile.sipf_baf': 'purchase.order.sipf.baf',
                            'sipf_profile.sipf_bssi': 'purchase.order.sipf.bssi',
                            'sipf_profile.sipf_cpau': 'purchase.order.sipf.cpau',
                            'sipf_profile.sipf_dpo': 'purchase.order.sipf.dpo',
                            'sipf_profile.sipf_infra': 'purchase.order.sipf.infra',
                            'sipf_profile.sipf_projects': 'purchase.order.sipf.projects',
                            'sipf_profile.sipf_silog': 'purchase.order.sipf.silog'
                        }
                        if ref_sequence_list != {}:
                            for ref, seq in ref_sequence_list.items():
                                # Set the sequence number regarding the department
                                if self.env.ref(ref).id == self.department_id.id:
                                    self.ref = (
                                        self.env['ir.sequence']
                                        .next_by_code(seq, sequence_date=seq_date)
                                    )
                    else:
                        raise UserError(
                            _('The department must be filled.'))

        return res

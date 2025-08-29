from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        """ Empêche l'ajout automatique du partner_id aux followers. """
        if partner_ids:
            # Filtrer : retirer le partner_id s'il est celui du record
            filtered_ids = []
            for partner_id in partner_ids:
                if not any(
                    hasattr(record, 'partner_id') and record.partner_id and record.partner_id.id == partner_id
                    for record in self
                ):
                    filtered_ids.append(partner_id)
            partner_ids = filtered_ids
        return super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)

# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import fields, models, _
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class ModelName(models.Model):
    _inherit = 'ir.rule'

    name = fields.Char()

    def _make_access_error(self, operation, records):
        _logger.info('Access Denied by record rules for operation: %s on record ids: %r, uid: %s, model: %s', operation, records.ids[:6], self._uid, records._name)

        model = records._name
        description = self.env['ir.model']._get(model).name or model
        msg_heads = {
            # Messages are declared in extenso so they are properly exported in translation terms
            'read':   _("Due to security restrictions, you are not allowed to access '%(document_kind)s' (%(document_model)s) records.", document_kind=description, document_model=model),
            'write':  _("Due to security restrictions, you are not allowed to modify '%(document_kind)s' (%(document_model)s) records.", document_kind=description, document_model=model),
            'create': _("Due to security restrictions, you are not allowed to create '%(document_kind)s' (%(document_model)s) records.", document_kind=description, document_model=model),
            'unlink': _("Due to security restrictions, you are not allowed to delete '%(document_kind)s' (%(document_model)s) records.", document_kind=description, document_model=model)
        }
        operation_error = msg_heads[operation]
        resolution_info = _("Contact your administrator to request access if necessary.")

        if not self.env.user.has_group('base.group_no_one') or not self.env.user.has_group('base.group_user'):
            msg = """{operation_error}

{resolution_info}""".format(
                operation_error=operation_error,
                resolution_info=resolution_info)
            return AccessError(msg)

        # This extended AccessError is only displayed in debug mode.
        # Note that by default, public and portal users do not have
        # the group "base.group_no_one", even if debug mode is enabled,
        # so it is relatively safe here to include the list of rules and record names.
        rules = self._get_failing(records, mode=operation).sudo()

        if model == 'hr.employee':
            records_description = ', '.join(['%s (id=%s)' % ('Information cachée', rec.id) for rec in records[:6].sudo()])
        else:
            records_description = ', '.join(['%s (id=%s)' % (rec.display_name, rec.id) for rec in records[:6].sudo()])
        failing_records = _("Records: %s", records_description)

        user_description = '%s (id=%s)' % (self.env.user.name, self.env.user.id)
        failing_user = _("User: %s", user_description)

        rules_description = '\n'.join('- %s' % rule.name for rule in rules)
        failing_rules = _("This restriction is due to the following rules:\n%s", rules_description)
        if any('company_id' in (r.domain_force or []) for r in rules):
            failing_rules += "\n\n" + _('Note: this might be a multi-company issue.')

        msg = """{operation_error}

{failing_records}
{failing_user}

{failing_rules}

{resolution_info}""".format(
                operation_error=operation_error,
                failing_records=failing_records,
                failing_user=failing_user,
                failing_rules=failing_rules,
                resolution_info=resolution_info)

        # clean up the cache of records prefetched with display_name above
        for record in records[:6]:
            record._cache.clear()

        return AccessError(msg)

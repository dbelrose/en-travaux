from odoo import models, api

import os
import datetime
import logging
import psycopg2

from odoo import _
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT

from odoo.addons.base_import.models.base_import import FIELDS_RECURSION_LIMIT

_logger = logging.getLogger(__name__)


class VolPublicAerodromeImportWizard(models.TransientModel):
    _name = 'manureva.vol_public_aerodrome_import_wizard'
    _description = 'Vols de transport aérien public – Aérodrome - Import - Wizard'
    _inherit = "base_import.import"

    @api.model
    def get_fields(self, model, depth=FIELDS_RECURSION_LIMIT):
        fields = super(VolPublicAerodromeImportWizard, self).get_fields(model, depth=depth)
        fields.extend([{
            'id': 'unique_import_id',
            'name': 'unique_import_id',
            'string': 'Import ID',
            'required': False,
            'fields': [],
            'type': 'char',
        }, {
            'id': 'balance',
            'name': 'balance',
            'string': 'Cumulative Balance',
            'required': False,
            'fields': [],
            'type': 'monetary',
        }])
        return fields

    def _parse_float(self, value):
        return float(value) if value else 0.0

    def _prepare_statement(self):
        date = datetime.date.today().strftime(DEFAULT_SERVER_DATE_FORMAT)
        filename = self.file_name and os.path.splitext(self.file_name)[0] or ""
        return self.env['manureva.vol_public_aerodrome'].create({
            'journal_id': self.env.context.get('journal_id', False),
            'name': _("%s - Import %s") % (date, filename),
            'reference': self.file_name})

    def _update_statement(self, data, import_fields, options):
        vals = {}
        date_index = import_fields.index('date') if 'date' in import_fields else False
        balance_index = import_fields.index('balance') if 'balance' in import_fields else False
        statment_index = import_fields.index('statement_id/.id')
        if date_index:
            vals['date'] = data[len(data) - 1][date_index]
        if balance_index:
            self._parse_float_from_data(data, balance_index, 'balance', options)
            vals['balance_start'] = self._parse_float(data[0][balance_index])
            vals['balance_end_real'] = self._parse_float(data[len(data) - 1][balance_index])
        self.env['manureva.vol_public_aerodrome'].browse(data[0][statment_index]).write(vals)

    @api.model
    def _convert_import_data(self, fields, options):
        data, import_fields = super(VolPublicAerodromeImportWizard, self)._convert_import_data(fields, options)
        import_fields.append('sequence')
        import_fields.append('statement_id/.id')
        for index, row in enumerate(data):
            row.append(index)
            row.append(self.env.context.get('bank_statement_id'))
        return data, import_fields

    def _parse_import_data(self, data, import_fields, options):
        parsed_data = super(VolPublicAerodromeImportWizard, self)._parse_import_data(data, import_fields, options)
        self._update_statement(parsed_data, import_fields, options)
        balance_index = import_fields.index('balance') if 'balance' in import_fields else False
        amount_index = import_fields.index('amount') if 'amount' in import_fields else False
        bank_data = []
        for row in parsed_data:
            if row[amount_index]:
                if balance_index:
                    del row[balance_index]
                bank_data.append(row)
        if balance_index:
            import_fields.remove('balance')
        return bank_data

    def do(self, fields, columns, options, dryrun=False):
        self._cr.execute('SAVEPOINT import_bank_statement')
        bank_statement = self._prepare_statement()
        res = super(
            VolPublicAerodromeImportWizard,
            self.with_context(bank_statement_id=bank_statement.id)
        ).do(fields, columns, options, dryrun=dryrun)
        try:
            if dryrun:
                self._cr.execute('ROLLBACK TO SAVEPOINT import_bank_statement')
            else:
                res.update({'bank_statement_id': bank_statement.id})
                self._cr.execute('RELEASE SAVEPOINT import_bank_statement')
        except psycopg2.InternalError as e:
            _logger.debug(e)
        return res

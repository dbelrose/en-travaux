# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Migration post-installation : Lier les réservations aux trimestres"""

    from odoo import registry, SUPERUSER_ID
    from odoo.api import Environment

    env = Environment(cr, SUPERUSER_ID, {})

    _logger.info("=== DÉBUT MIGRATION : Liaison trimestres ===")

    # Corriger les status
    lines_without_status = env['booking.import.line'].search([
        '|', ('status', '=', False), ('status', '=', None)
    ])
    if lines_without_status:
        lines_without_status.write({'status': 'ok'})
        _logger.info(f"✓ {len(lines_without_status)} status corrigés")

    # Lier aux trimestres
    all_lines = env['booking.import.line'].search([
        ('arrival_date', '!=', False),
        ('property_type_id', '!=', False),
        ('booking_quarter_id', '=', False)
    ])

    _logger.info(f"Liaison de {len(all_lines)} réservations...")

    linked = 0
    for line in all_lines:
        year = line.arrival_date.year
        month = line.arrival_date.month
        quarter = str(((month - 1) // 3) + 1)

        quarter_record = env['booking.quarter'].search([
            ('year', '=', year),
            ('quarter', '=', quarter),
            ('property_type_id', '=', line.property_type_id.id),
            ('company_id', '=', line.company_id.id)
        ], limit=1)

        if not quarter_record:
            quarter_record = env['booking.quarter'].create({
                'year': year,
                'quarter': quarter,
                'property_type_id': line.property_type_id.id,
                'company_id': line.company_id.id
            })

        line.booking_quarter_id = quarter_record.id
        linked += 1

    _logger.info(f"✓ {linked} réservations liées")

    # Recalculer
    all_quarters = env['booking.quarter'].search([])
    for q in all_quarters:
        q._compute_nights_data()

    _logger.info(f"✓ {len(all_quarters)} trimestres recalculés")
    _logger.info("=== FIN MIGRATION ===")
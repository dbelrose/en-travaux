# -*- coding: utf-8 -*-
"""
Migration : supplier.email.rule
Char → Many2one pour product_attribute_name et tantieme_attribute_name

À placer dans :
  migrations/17.0.3.1.0/post-migrate.py
  (ou exécuter manuellement une fois via le shell Odoo)
"""

import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Pour chaque règle existante, recherche le product.attribute
    dont le nom correspond à la valeur texte stockée, et renseigne
    les nouveaux champs Many2one.
    Laisse NULL si aucune correspondance (à corriger manuellement).
    """
    cr.execute("""
        SELECT id, product_attribute_name, tantieme_attribute_name
        FROM supplier_email_rule
        WHERE product_attribute_name IS NOT NULL
           OR tantieme_attribute_name IS NOT NULL
    """)
    rows = cr.fetchall()
    _logger.info("Migration supplier.email.rule : %d règle(s) à traiter.", len(rows))

    for rule_id, attr_name, tantieme_name in rows:
        # product_attribute_id
        if attr_name:
            cr.execute(
                "SELECT id FROM product_attribute WHERE name = %s LIMIT 1",
                (attr_name,)
            )
            row = cr.fetchone()
            if row:
                cr.execute(
                    "UPDATE supplier_email_rule SET product_attribute_id = %s WHERE id = %s",
                    (row[0], rule_id)
                )
                _logger.info(
                    "  Règle %d : product_attribute_id = %d ('%s')",
                    rule_id, row[0], attr_name
                )
            else:
                _logger.warning(
                    "  Règle %d : attribut '%s' introuvable — à corriger manuellement.",
                    rule_id, attr_name
                )

        # tantieme_attribute_id
        if tantieme_name:
            cr.execute(
                "SELECT id FROM product_attribute WHERE name = %s LIMIT 1",
                (tantieme_name,)
            )
            row = cr.fetchone()
            if row:
                cr.execute(
                    "UPDATE supplier_email_rule SET tantieme_attribute_id = %s WHERE id = %s",
                    (row[0], rule_id)
                )
                _logger.info(
                    "  Règle %d : tantieme_attribute_id = %d ('%s')",
                    rule_id, row[0], tantieme_name
                )
            else:
                _logger.warning(
                    "  Règle %d : attribut tantième '%s' introuvable — à corriger manuellement.",
                    rule_id, tantieme_name
                )

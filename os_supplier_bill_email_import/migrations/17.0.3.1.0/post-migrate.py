# -*- coding: utf-8 -*-
"""
Migration : supplier.email.rule
Char → Many2one pour product_attribute_name et tantieme_attribute_name

À placer dans :
  migrations/17.0.3.1.0/post-migrate.py
  (ou exécuter manuellement une fois via le shell Odoo)

Mis à jour v3.3 :
  Ajout d'une vérification d'existence des colonnes sources avant toute
  lecture — évite l'erreur "UndefinedColumn" lorsque la migration a déjà
  été appliquée lors d'une mise à jour précédente (idempotence).
"""

import logging
_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    """Retourne True si la colonne existe dans la table."""
    cr.execute("""
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
    """, (table, column))
    return cr.fetchone() is not None


def migrate(cr, version):
    """
    Pour chaque règle existante, recherche le product.attribute
    dont le nom correspond à la valeur texte stockée, et renseigne
    les nouveaux champs Many2one.
    Laisse NULL si aucune correspondance (à corriger manuellement).

    La migration est idempotente : si les colonnes sources
    product_attribute_name / tantieme_attribute_name n'existent plus
    (déjà migrées), elle s'arrête immédiatement sans erreur.
    """
    has_attr_name = _column_exists(cr, 'supplier_email_rule', 'product_attribute_name')
    has_tantieme_name = _column_exists(cr, 'supplier_email_rule', 'tantieme_attribute_name')

    if not has_attr_name and not has_tantieme_name:
        _logger.info(
            "Migration 17.0.3.1.0 supplier.email.rule : "
            "colonnes sources absentes — migration déjà appliquée, rien à faire."
        )
        return

    # Construction dynamique de la liste de colonnes à lire
    select_cols = ['id']
    if has_attr_name:
        select_cols.append('product_attribute_name')
    if has_tantieme_name:
        select_cols.append('tantieme_attribute_name')

    where_clauses = []
    if has_attr_name:
        where_clauses.append('product_attribute_name IS NOT NULL')
    if has_tantieme_name:
        where_clauses.append('tantieme_attribute_name IS NOT NULL')

    query = "SELECT %s FROM supplier_email_rule WHERE %s" % (
        ', '.join(select_cols),
        ' OR '.join(where_clauses),
    )
    cr.execute(query)
    rows = cr.fetchall()
    _logger.info("Migration supplier.email.rule : %d règle(s) à traiter.", len(rows))

    col_index = {col: i for i, col in enumerate(select_cols)}

    for row in rows:
        rule_id = row[col_index['id']]
        attr_name = row[col_index['product_attribute_name']] if has_attr_name else None
        tantieme_name = row[col_index['tantieme_attribute_name']] if has_tantieme_name else None

        # product_attribute_id
        if attr_name:
            cr.execute(
                "SELECT id FROM product_attribute WHERE name = %s LIMIT 1",
                (attr_name,)
            )
            result = cr.fetchone()
            if result:
                cr.execute(
                    "UPDATE supplier_email_rule SET product_attribute_id = %s WHERE id = %s",
                    (result[0], rule_id)
                )
                _logger.info(
                    "  Règle %d : product_attribute_id = %d ('%s')",
                    rule_id, result[0], attr_name
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
            result = cr.fetchone()
            if result:
                cr.execute(
                    "UPDATE supplier_email_rule SET tantieme_attribute_id = %s WHERE id = %s",
                    (result[0], rule_id)
                )
                _logger.info(
                    "  Règle %d : tantieme_attribute_id = %d ('%s')",
                    rule_id, result[0], tantieme_name
                )
            else:
                _logger.warning(
                    "  Règle %d : attribut tantième '%s' introuvable — à corriger manuellement.",
                    rule_id, tantieme_name
                )

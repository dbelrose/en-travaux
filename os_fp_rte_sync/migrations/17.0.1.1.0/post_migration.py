# migrations/16.0.1.3.0/post-migration.py
from odoo import api, SUPERUSER_ID

INDEX_NAME = "uniq_idnum_rte_etab_name"


def _ensure_rte_etab_category(env):
    Cat = env["res.partner.id_category"].sudo()
    if "code" in Cat._fields:
        cat = Cat.search([("code", "=", "rte_etab")], limit=1)
    else:
        cat = Cat.search([("name", "=", "RTE_ETAB")], limit=1)
    if not cat:
        vals = {"name": "RTE_ETAB"}
        if "code" in Cat._fields:
            vals["code"] = "rte_etab"
        cat = Cat.create(vals)
    return cat.id

def migrate(cr, version):
    """Création de l'index UNIQUE partiel sur upgrade (idempotent)."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    cid = _ensure_rte_etab_category(env)

    cr.execute(f"""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = ANY (current_schemas(true))
          AND indexname = '{INDEX_NAME}'
      ) THEN
        EXECUTE '
          CREATE UNIQUE INDEX {INDEX_NAME}
          ON res_partner_id_number (name)
          WHERE category_id = {cid}
        ';
      END IF;
    END$$;
    """)

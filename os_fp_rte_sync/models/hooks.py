from odoo import api, SUPERUSER_ID

INDEX_NAME = "uniq_idnum_rte_etab_name"


def _ensure_rte_etab_category(env):
    """Récupère (ou crée) la catégorie d'identifiant 'rte_etab'."""
    Cat = env["res.partner.id_category"].sudo()
    # Si le champ 'code' existe, on s'y appuie ; sinon fallback sur 'name'
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


def post_init_hook(arg, *args, **kwargs):
    """
    Compatible :
      - Odoo 17 : post_init_hook(cr, registry)
      - Odoo 18+ : post_init_hook(env)
    """
    if hasattr(arg, "cr"):          # Odoo 18+ : arg est un Environment
        env = arg
    else:                            # Odoo 17 : arg = cr et args[0] = registry
        cr, registry = arg, args[0]
        env = api.Environment(cr, SUPERUSER_ID, {})

    cid = _ensure_rte_etab_category(env)

    # DO + EXECUTE pour créer l'index UNIQUE partiel une seule fois.
    # Pas de CONCURRENTLY dans un post_init (transaction en cours).
    env.cr.execute(f"""
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


def uninstall_hook(cr, registry):
    # Suppression idempotente à la désinstallation
    cr.execute(f"DROP INDEX IF EXISTS {INDEX_NAME};")

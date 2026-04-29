"""
Migration 17.0.1.0.0 → 17.0.2.0.0
Ajoute les colonnes manquantes sur res_partner et crée la table user.encrypted.field.pref.
"""


def migrate(cr, version):
    # 1. Colonne de recherche semi-aveugle sur res_partner
    cr.execute("""
        ALTER TABLE res_partner
        ADD COLUMN IF NOT EXISTS name_search_tokens TEXT;
    """)

    # 2. Index pour accélérer la recherche sur les tokens
    cr.execute("""
        CREATE INDEX IF NOT EXISTS res_partner_name_search_tokens_idx
        ON res_partner USING gin(to_tsvector('simple', coalesce(name_search_tokens, '')));
    """)

    # 3. Table des préférences utilisateur par champ
    cr.execute("""
        CREATE TABLE IF NOT EXISTS user_encrypted_field_pref (
            id          SERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES res_users(id) ON DELETE CASCADE,
            field_name  VARCHAR NOT NULL,
            enabled     BOOLEAN NOT NULL DEFAULT TRUE,
            UNIQUE (user_id, field_name)
        );
    """)

    # 4. Colonne mandatory sur encrypted_field_config (si le module était déjà installé)
    cr.execute("""
        ALTER TABLE encrypted_field_config
        ADD COLUMN IF NOT EXISTS mandatory BOOLEAN NOT NULL DEFAULT FALSE;
    """)

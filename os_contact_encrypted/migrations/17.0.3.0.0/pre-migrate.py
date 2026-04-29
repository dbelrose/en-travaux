"""
Migration 17.0.2.0.0 → 17.0.3.0.0

Crée la table satellite partner_crypto_data et migre les données
chiffrées depuis les anciennes colonnes _os_enc de res.partner
(si elles existent — installation fraîche : rien à faire).

Après migration, les colonnes _os_enc sont laissées en place
(DROP non effectué pour sécurité) — elles peuvent être supprimées
manuellement une fois la migration validée.
"""
import logging

_logger = logging.getLogger(__name__)

ENCRYPTED_FIELDS = [
    'phone', 'mobile', 'email', 'name',
    'street', 'vat', 'website', 'comment',
]


def migrate(cr, version):
    _logger.info('[os_contact_encrypted] Migration v3 : création table satellite')

    # 1. Créer la table satellite
    cr.execute("""
        CREATE TABLE IF NOT EXISTS partner_crypto_data (
            id          SERIAL PRIMARY KEY,
            partner_id  INTEGER NOT NULL REFERENCES res_partner(id) ON DELETE CASCADE,
            company_id  INTEGER NOT NULL REFERENCES res_company(id),
            field_name  VARCHAR NOT NULL,
            value_enc   TEXT,
            token       VARCHAR,
            owner_id    INTEGER NOT NULL REFERENCES res_users(id),
            UNIQUE (partner_id, field_name, company_id)
        );
        CREATE INDEX IF NOT EXISTS partner_crypto_data_partner_idx
            ON partner_crypto_data(partner_id);
        CREATE INDEX IF NOT EXISTS partner_crypto_data_token_idx
            ON partner_crypto_data(token);
        CREATE INDEX IF NOT EXISTS partner_crypto_data_owner_idx
            ON partner_crypto_data(owner_id);
    """)

    # 2. Vérifier si les colonnes _os_enc existent (installation depuis v1/v2)
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_partner'
          AND column_name LIKE '%_os_enc'
    """)
    existing_enc_cols = [row[0] for row in cr.fetchall()]

    if not existing_enc_cols:
        _logger.info('[os_contact_encrypted] Aucune colonne _os_enc — installation fraîche, rien à migrer.')
        return

    # 3. Récupérer la société par défaut
    cr.execute("SELECT id FROM res_company ORDER BY id LIMIT 1")
    row = cr.fetchone()
    if not row:
        _logger.warning('[os_contact_encrypted] Aucune société trouvée, migration des données abandonnée.')
        return
    default_company_id = row[0]

    # 4. Récupérer l'admin comme owner par défaut
    cr.execute("SELECT id FROM res_users WHERE active = true ORDER BY id LIMIT 1")
    row = cr.fetchone()
    default_owner_id = row[0] if row else 1

    # 5. Migrer les données chiffrées existantes
    migrated = 0
    for col in existing_enc_cols:
        # col = 'phone_os_enc' → field_name = 'phone'
        field_name = col.replace('_os_enc', '')

        # Utiliser crypto_owner_id si disponible
        has_owner_col = False
        cr.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'res_partner' AND column_name = 'crypto_owner_id'
        """)
        has_owner_col = bool(cr.fetchone())

        owner_select = 'COALESCE(p.crypto_owner_id, %s)' % default_owner_id if has_owner_col else str(default_owner_id)

        # Token de recherche : récupérer depuis name_search_tokens si champ = name
        token_select = 'p.name_search_tokens' if field_name == 'name' else 'NULL'
        has_token_col = False
        if field_name == 'name':
            cr.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'res_partner' AND column_name = 'name_search_tokens'
            """)
            has_token_col = bool(cr.fetchone())
        if not has_token_col:
            token_select = 'NULL'

        cr.execute(f"""
            INSERT INTO partner_crypto_data
                (partner_id, company_id, field_name, value_enc, token, owner_id)
            SELECT
                p.id,
                {default_company_id},
                %s,
                p.{col},
                {token_select},
                {owner_select}
            FROM res_partner p
            WHERE p.{col} IS NOT NULL AND p.{col} != ''
            ON CONFLICT (partner_id, field_name, company_id) DO UPDATE
                SET value_enc = EXCLUDED.value_enc,
                    token     = EXCLUDED.token,
                    owner_id  = EXCLUDED.owner_id
        """, (field_name,))
        count = cr.rowcount
        migrated += count
        _logger.info('[os_contact_encrypted] %s : %d enregistrements migrés', field_name, count)

    _logger.info(
        '[os_contact_encrypted] Migration v3 terminée : %d enregistrements déplacés vers partner_crypto_data. '
        'Les colonnes _os_enc de res_partner sont conservées (suppression manuelle possible après validation).',
        migrated
    )

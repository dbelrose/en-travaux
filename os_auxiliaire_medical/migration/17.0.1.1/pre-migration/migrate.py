"""
Migration vers la version incluant :
  - cps.api.usage         : suivi des tokens Anthropic
  - cps.bordereau.modele  : gabarits de documents pour les bordereaux
  - cps.acte.type.company_id + is_company_override
  - cps.bordereau.modele_id
  - cps.ordonnance.ligne.nb_seances (valeur par défaut depuis acte_type)
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # ── 1. Colonne company_id sur cps.acte.type ───────────────────────────────
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'cps_acte_type'
          AND column_name = 'company_id'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de company_id sur cps_acte_type")
        cr.execute("""
            ALTER TABLE cps_acte_type
            ADD COLUMN company_id INTEGER REFERENCES res_company(id) ON DELETE SET NULL
        """)
        cr.execute("""
            CREATE INDEX idx_cps_acte_type_company ON cps_acte_type(company_id)
        """)

    # ── 2. Colonne is_company_override sur cps.acte.type ─────────────────────
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'cps_acte_type'
          AND column_name = 'is_company_override'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de is_company_override sur cps_acte_type")
        cr.execute("""
            ALTER TABLE cps_acte_type
            ADD COLUMN is_company_override BOOLEAN DEFAULT FALSE NOT NULL
        """)

    # ── 3. Colonne sequence sur cps.acte.type ─────────────────────────────────
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'cps_acte_type'
          AND column_name = 'sequence'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de sequence sur cps_acte_type")
        cr.execute("""
            ALTER TABLE cps_acte_type
            ADD COLUMN sequence INTEGER DEFAULT 10 NOT NULL
        """)

    # ── 4. Table cps_bordereau_modele ──────────────────────────────────────────
    cr.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'cps_bordereau_modele'
    """)
    if not cr.fetchone():
        _logger.info("Migration: création de la table cps_bordereau_modele")
        cr.execute("""
            CREATE TABLE cps_bordereau_modele (
                id                      SERIAL PRIMARY KEY,
                name                    VARCHAR NOT NULL,
                sequence                INTEGER DEFAULT 10 NOT NULL,
                active                  BOOLEAN DEFAULT TRUE NOT NULL,
                is_default              BOOLEAN DEFAULT FALSE NOT NULL,
                company_id              INTEGER REFERENCES res_company(id) ON DELETE SET NULL,
                entete_texte            TEXT,
                pied_page_texte         TEXT,
                mention_complementaire  TEXT,
                afficher_dn             BOOLEAN DEFAULT TRUE NOT NULL,
                afficher_date_naissance BOOLEAN DEFAULT FALSE NOT NULL,
                afficher_date_debut     BOOLEAN DEFAULT TRUE NOT NULL,
                afficher_date_fin       BOOLEAN DEFAULT TRUE NOT NULL,
                afficher_nb_actes       BOOLEAN DEFAULT FALSE NOT NULL,
                afficher_part_cps       BOOLEAN DEFAULT TRUE NOT NULL,
                afficher_part_patient   BOOLEAN DEFAULT TRUE NOT NULL,
                afficher_total_ligne    BOOLEAN DEFAULT FALSE NOT NULL,
                couleur_principale      VARCHAR DEFAULT '1F6B3A',
                notes                   TEXT,
                create_uid              INTEGER REFERENCES res_users(id),
                write_uid               INTEGER REFERENCES res_users(id),
                create_date             TIMESTAMP,
                write_date              TIMESTAMP
            )
        """)
        # Modèle par défaut (partagé)
        cr.execute("""
            INSERT INTO cps_bordereau_modele
              (name, sequence, active, is_default, entete_texte, couleur_principale)
            VALUES
              ('Modèle standard CPS', 10, TRUE, TRUE,
               'BORDEREAU DE FACTURATION MENSUEL\nCaisse de Prévoyance Sociale – Polynésie française',
               '1F6B3A')
        """)

    # ── 5. Colonne modele_id sur cps_bordereau ────────────────────────────────
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'cps_bordereau'
          AND column_name = 'modele_id'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de modele_id sur cps_bordereau")
        cr.execute("""
            ALTER TABLE cps_bordereau
            ADD COLUMN modele_id INTEGER
                REFERENCES cps_bordereau_modele(id) ON DELETE SET NULL
        """)

    # ── 6. Table cps_api_usage ─────────────────────────────────────────────────
    cr.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'cps_api_usage'
    """)
    if not cr.fetchone():
        _logger.info("Migration: création de la table cps_api_usage")
        cr.execute("""
            CREATE TABLE cps_api_usage (
                id              SERIAL PRIMARY KEY,
                user_id         INTEGER NOT NULL REFERENCES res_users(id),
                company_id      INTEGER NOT NULL REFERENCES res_company(id),
                date            TIMESTAMP NOT NULL DEFAULT NOW(),
                model           VARCHAR NOT NULL,
                operation       VARCHAR NOT NULL,
                ordonnance_id   INTEGER REFERENCES cps_ordonnance(id) ON DELETE SET NULL,
                input_tokens    INTEGER DEFAULT 0,
                output_tokens   INTEGER DEFAULT 0,
                total_tokens    INTEGER DEFAULT 0,
                success         BOOLEAN DEFAULT TRUE,
                error_message   VARCHAR,
                create_uid      INTEGER REFERENCES res_users(id),
                write_uid       INTEGER REFERENCES res_users(id),
                create_date     TIMESTAMP,
                write_date      TIMESTAMP
            )
        """)
        cr.execute("""
            CREATE INDEX idx_cps_api_usage_user    ON cps_api_usage(user_id);
            CREATE INDEX idx_cps_api_usage_company ON cps_api_usage(company_id);
            CREATE INDEX idx_cps_api_usage_date    ON cps_api_usage(date);
        """)

    _logger.info("Migration CPS terminée avec succès.")

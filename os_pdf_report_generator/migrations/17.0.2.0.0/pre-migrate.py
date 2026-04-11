import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration 17.0.1.0.0 -> 17.0.2.0.0
    Ajoute les colonnes manquantes introduites par la v2 du module.
    Ce script pre-migrate s'exécute AVANT que l'ORM ne charge les modèles,
    ce qui évite l'erreur "column does not exist" au démarrage.
    """

    # 1. res_company.pdf_print_credits
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'pdf_print_credits'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de res_company.pdf_print_credits")
        cr.execute("""
            ALTER TABLE res_company
            ADD COLUMN pdf_print_credits INTEGER NOT NULL DEFAULT 0
        """)
    else:
        _logger.info("Migration: res_company.pdf_print_credits existe déjà, ignoré.")

    # 2. pdf_report_config.technical_report_name
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'pdf_report_config'
          AND column_name = 'technical_report_name'
    """)
    if not cr.fetchone():
        _logger.info("Migration: ajout de pdf_report_config.technical_report_name")
        cr.execute("""
            ALTER TABLE pdf_report_config
            ADD COLUMN technical_report_name VARCHAR
        """)
        # Remplir le champ pour les enregistrements existants
        cr.execute("""
            UPDATE pdf_report_config
            SET technical_report_name = 'os_pdf_report_generator.pdf_report_' || id::text
            WHERE technical_report_name IS NULL
        """)
        _logger.info("Migration: technical_report_name rempli pour les enregistrements existants.")
    else:
        _logger.info("Migration: pdf_report_config.technical_report_name existe déjà, ignoré.")

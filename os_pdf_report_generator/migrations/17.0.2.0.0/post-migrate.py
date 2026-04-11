import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Migration 17.0.2.0.0 — post-migrate
    S'exécute après que l'ORM a initialisé les tables, aussi bien lors d'une
    mise à jour (upgrade) que d'une première installation (install).

    Garantit la présence des colonnes introduites en v2 et remplit
    rétroactivement les enregistrements existants.
    """

    # 1. res_company.pdf_print_credits
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'pdf_print_credits'
    """)
    if not cr.fetchone():
        _logger.info("post-migrate: ajout colonne res_company.pdf_print_credits")
        cr.execute("""
            ALTER TABLE res_company
            ADD COLUMN pdf_print_credits INTEGER NOT NULL DEFAULT 0
        """)
    else:
        _logger.info("post-migrate: res_company.pdf_print_credits déjà présente.")

    # 2. pdf_report_config.technical_report_name
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'pdf_report_config'
          AND column_name = 'technical_report_name'
    """)
    if not cr.fetchone():
        _logger.info("post-migrate: ajout colonne pdf_report_config.technical_report_name")
        cr.execute("""
            ALTER TABLE pdf_report_config
            ADD COLUMN technical_report_name VARCHAR
        """)

    # Remplir pour les enregistrements existants qui auraient une valeur NULL
    cr.execute("""
        UPDATE pdf_report_config
        SET technical_report_name = 'os_pdf_report_generator.pdf_report_' || id::text
        WHERE technical_report_name IS NULL OR technical_report_name = ''
    """)
    cr.execute("SELECT COUNT(*) FROM pdf_report_config WHERE technical_report_name IS NOT NULL")
    count = cr.fetchone()[0]
    _logger.info("post-migrate: %d enregistrement(s) pdf_report_config mis à jour.", count)

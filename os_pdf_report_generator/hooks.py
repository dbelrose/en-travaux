import logging

_logger = logging.getLogger(__name__)

# hooks.py
def pre_init_hook(env):
    cr = env.cr
    cr.execute("""
        ALTER TABLE res_company
        ADD COLUMN IF NOT EXISTS pdf_print_credits INTEGER NOT NULL DEFAULT 0
    """)
    cr.execute("""
        ALTER TABLE pdf_report_config
        ADD COLUMN IF NOT EXISTS technical_report_name VARCHAR
    """)
    cr.execute("""
        UPDATE pdf_report_config
        SET technical_report_name = 'os_pdf_report_generator.pdf_report_' || id::text
        WHERE technical_report_name IS NULL OR technical_report_name = ''
    """)

# def pre_init_hook(env):
#     """
#     Crée les colonnes nécessaires avant que l'ORM ne charge les modèles.
#     Exécuté lors de l'installation ET de chaque mise à jour du module.
#     """
#     cr = env.cr
#
#     # 1. res_company.pdf_print_credits
#     cr.execute("""
#         SELECT column_name FROM information_schema.columns
#         WHERE table_name = 'res_company' AND column_name = 'pdf_print_credits'
#     """)
#     if not cr.fetchone():
#         _logger.info("pre_init_hook: création de res_company.pdf_print_credits")
#         cr.execute("""
#             ALTER TABLE res_company
#             ADD COLUMN pdf_print_credits INTEGER NOT NULL DEFAULT 0
#         """)
#
#     # 2. pdf_report_config.technical_report_name
#     cr.execute("""
#         SELECT column_name FROM information_schema.columns
#         WHERE table_name = 'pdf_report_config' AND column_name = 'technical_report_name'
#     """)
#     if not cr.fetchone():
#         _logger.info("pre_init_hook: création de pdf_report_config.technical_report_name")
#         cr.execute("""
#             ALTER TABLE pdf_report_config
#             ADD COLUMN technical_report_name VARCHAR
#         """)
#
#     # Remplir rétroactivement les enregistrements existants
#     cr.execute("""
#         UPDATE pdf_report_config
#         SET technical_report_name = 'os_pdf_report_generator.pdf_report_' || id::text
#         WHERE technical_report_name IS NULL OR technical_report_name = ''
#     """)

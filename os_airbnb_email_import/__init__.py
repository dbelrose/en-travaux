# -*- coding: utf-8 -*-
from . import models

import logging

_logger = logging.getLogger(__name__)


def pre_init_hook(cr):
    """
    Hook appelé AVANT l'installation/mise à jour du module
    Permet de préparer la base de données
    """
    _logger.info("🔧 Pre-init hook: Ajout du champ airbnb_sender_emails")

    # Vérifier si la colonne existe déjà
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='res_company' 
        AND column_name='airbnb_sender_emails'
    """)

    if not cr.fetchone():
        # La colonne n'existe pas, on la crée
        cr.execute("""
            ALTER TABLE res_company 
            ADD COLUMN airbnb_sender_emails VARCHAR
        """)
        _logger.info("✅ Colonne airbnb_sender_emails créée")
    else:
        _logger.info("ℹ️ Colonne airbnb_sender_emails existe déjà")


def post_init_hook(cr, registry):
    """
    Hook appelé APRÈS l'installation/mise à jour du module
    Permet de faire des configurations post-installation
    """
    _logger.info("🔧 Post-init hook: Configuration initiale")

    # Définir une valeur par défaut pour les sociétés existantes
    cr.execute("""
        UPDATE res_company 
        SET airbnb_sender_emails = 'automated@airbnb.com' 
        WHERE airbnb_sender_emails IS NULL
    """)

    _logger.info("✅ Valeurs par défaut configurées")

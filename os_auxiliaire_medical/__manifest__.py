{
    'name': 'Auxiliaire Médical CPS – Polynésie française',
    'version': '17.0.2.2.0',
    'author': 'OpalSea',
    'website': 'https://opalsea.site',
    'category': 'Healthcare',
    'summary': 'Gestion des feuilles de soins, ordonnances et bordereaux CPS (Polynésie fr.)',
    'depends': [
        'base',
        'l10n_pf',
        'mail',
        'account',
        'base_setup',
        'partner_firstname',  # Décommentez si le module est installé
    ],
    'data': [
        # ── Sécurité ────────────────────────────────────────────────
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule_multi_company.xml',   # ← NOUVEAU (fix multi-société)

        # ── Séquences ───────────────────────────────────────────────
        'data/ir_sequence_data.xml',

        # ── Données de base ─────────────────────────────────────────
        'data/res_partner_category_data.xml',
        'data/cps_acte_type_orthophoniste_data.xml',
        'data/cps_acte_type_orthoptiste_data.xml',
        'data/cps_acte_type_pedicure_data.xml',
        'data/cps_acte_type_infirmier_data.xml',
        'data/cps_acte_type_kinesitherapeute_data.xml',

        # ── Vues ────────────────────────────────────────────────────
        'views/acte_type_server_action.xml',
        'views/feuille_modele_views.xml',
        'views/feuille_soins_views.xml',
        'views/tarif_historique_views.xml',

        'views/res_partner_cps_views.xml',      # ← FIX libellé VAT + multi-société
        'views/acte_type_views.xml',            # ← FIX filtre profession + personnalisation société
        'views/ordonnance_views.xml',           # ← FIX quantité par défaut
        'views/bordereau_modele_views.xml',     # ← NOUVEAU
        'views/bordereau_views.xml',            # ← NOUVEAU sélection modèle document
        'views/api_usage_views.xml',            # ← NOUVEAU comptage tokens
        'views/res_config_settings_views.xml',  # ← NOUVEAU sélection modèle Claude

        'wizards/wizard_bordereau_views.xml',
        'wizards/wizard_date_selection_views.xml',
        'wizards/wizard_ocr_ordonnance_views.xml',

        # ── Rapports ────────────────────────────────────────────────
        'report/report_bordereau.xml',
        'report/report_feuille_soins.xml',
        'report/report_facture_mutuelle.xml',

        # ── Menus ───────────────────────────────────────────────────
        'views/menu_views.xml',
    ],
    'demo': [
        'demo/demo_data.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

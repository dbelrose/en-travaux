from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Recherche ZK ──────────────────────────────────────────────────────────
    crypto_min_search_prefix_len = fields.Integer(
        string='Longueur minimale préfixe recherche ZK',
        default=3,
        config_parameter='os_contact_encrypted.min_search_prefix_len',
        help=(
            "Nombre minimum de caractères d'un mot pour déclencher la recherche "
            "dans les noms chiffrés (hors initiales, toujours acceptées).\n"
            "Exemple : 4 → 'Dupo' trouve 'Dupont', mais 'Du' ne trouve rien.\n"
            "Valeur recommandée : 3 ou 4. Min. 2, max. 8."
        ),
    )

    # ── Aperçu du nom ─────────────────────────────────────────────────────────
    crypto_display_name_chars = fields.Integer(
        string='Caractères du nom affichés (aperçu)',
        default=1,
        config_parameter='os_contact_encrypted.display_name_chars',
        help=(
            "Nombre de caractères du premier segment du nom visibles SANS déchiffrement.\n"
            "1 = initiales uniquement  →  D. J.  (confidentialité maximale)\n"
            "4 = 4 premières lettres + initiale prénom  →  Dupo. J.\n"
            "Cette valeur DOIT être ≤ à la longueur minimale du préfixe de recherche "
            "pour que l'aperçu et la recherche restent cohérents.\n"
            "Min. 1, max. 10."
        ),
    )

    @api.constrains('crypto_min_search_prefix_len', 'crypto_display_name_chars')
    def _check_crypto_settings(self):
        for rec in self:
            if rec.crypto_min_search_prefix_len < 2:
                raise models.ValidationError(
                    'La longueur minimale de préfixe doit être ≥ 2.')
            if rec.crypto_min_search_prefix_len > 8:
                raise models.ValidationError(
                    'La longueur minimale de préfixe doit être ≤ 8.')
            if rec.crypto_display_name_chars < 1:
                raise models.ValidationError(
                    "Le nombre de caractères d'aperçu doit être ≥ 1.")
            if rec.crypto_display_name_chars > 10:
                raise models.ValidationError(
                    "Le nombre de caractères d'aperçu doit être ≤ 10.")

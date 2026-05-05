from odoo import models, fields, api, exceptions
from odoo.addons.os_contact_encrypted.models.encrypted_field_config import ENCRYPTABLE_FIELDS
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

FIELD_NAMES = [f for f, _ in ENCRYPTABLE_FIELDS]
BLIND_TOKEN_LEN = 16   # 64 bits — non réversible, collision négligeable

# Masques visuels pour chaque type de champ (mode verrouillé, propriétaire sans MDP)
_FIELD_MASK_OWNER = {
    'phone':   '🔒 ── ── ── ──',
    'mobile':  '🔒 ── ── ── ──',
    'email':   '🔒 ────@────.──',
    'name':    None,              # Cas spécial : on affiche l'aperçu stocké
    'street':  '🔒 ─────────────',
    'vat':     '🔒 ─────────────',
    'website': '🔒 ────────────',
    'comment': '🔒 ─────────────',
}

# Masques pour les autres utilisateurs (non-propriétaires)
_FIELD_MASK_OTHER = {
    'phone':   '🔒',
    'mobile':  '🔒',
    'email':   '🔒',
    'name':    None,   # Cas spécial : on affiche l'aperçu (initiales) + cadenas
    'street':  '🔒',
    'vat':     '🔒',
    'website': '🔒',
    'comment': '🔒',
}

_LOCKED_PREFIXES = ('🔒', '⚠️', '████')


class ResPartner(models.Model):
    """
    Extension LÉGÈRE de res.partner — v3+ (architecture satellite).

    Nouveautés v3+ :
    - Recherche ZK multi-mots : intersection de tokens HMAC par mot-clé.
    - Longueur minimale de préfixe et nombre de caractères d'aperçu configurables
      dans Paramètres → Chiffrement contacts.
    - Champs display avec inverse : les champs chiffrés restent éditables
      (saisie d'une nouvelle valeur → re-chiffrement automatique).
    - Affichage partiel du nom (N premiers caractères + initiales), masque
      🔒 pour téléphone/email/etc.
    - phone_display et mobile_display correctement propagés en vue liste.
    """
    _inherit = 'res.partner'

    # ── Champs transients (store=False) ───────────────────────────────────────
    has_encrypted_data = fields.Boolean(
        string='Données chiffrées',
        compute='_compute_has_encrypted_data',
        store=False,
    )
    session_password = fields.Char(
        string='Mot de passe de déchiffrement',
        store=False,
        default=False,
    )

    # ── Champs d'affichage avec inverse (édition transparente) ───────────────
    phone_display = fields.Char(
        string='Téléphone',
        compute='_compute_display_fields',
        inverse='_inverse_phone_display',
        store=False,
    )
    mobile_display = fields.Char(
        string='Mobile',
        compute='_compute_display_fields',
        inverse='_inverse_mobile_display',
        store=False,
    )
    email_display = fields.Char(
        string='Email',
        compute='_compute_display_fields',
        inverse='_inverse_email_display',
        store=False,
    )
    name_display = fields.Char(
        string='Nom',
        compute='_compute_display_fields',
        inverse='_inverse_name_display',
        store=False,
    )
    street_display = fields.Char(
        string='Adresse',
        compute='_compute_display_fields',
        inverse='_inverse_street_display',
        store=False,
    )
    vat_display = fields.Char(
        string='N° fiscal',
        compute='_compute_display_fields',
        inverse='_inverse_vat_display',
        store=False,
    )
    website_display = fields.Char(
        string='Site web',
        compute='_compute_display_fields',
        inverse='_inverse_website_display',
        store=False,
    )
    comment_display = fields.Char(
        string='Notes',
        compute='_compute_display_fields',
        inverse='_inverse_comment_display',
        store=False,
    )

    # ── Paramètres de configuration ───────────────────────────────────────────
    def _get_min_search_prefix_len(self) -> int:
        """Longueur minimale du préfixe pour la recherche ZK (défaut 3)."""
        try:
            v = int(self.env['ir.config_parameter'].sudo().get_param(
                'os_contact_encrypted.min_search_prefix_len', '3'))
            return max(2, min(v, 8))
        except Exception:
            return 3

    def _get_display_name_chars(self) -> int:
        """Nombre de caractères du premier segment à afficher sans MDP (défaut 1)."""
        try:
            v = int(self.env['ir.config_parameter'].sudo().get_param(
                'os_contact_encrypted.display_name_chars', '1'))
            return max(1, min(v, 10))
        except Exception:
            return 1

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_crypto_map(self):
        """Retourne {field_name: partner.crypto.data record} pour ce partner."""
        return self.env['partner.crypto.data'].get_for_partner(self.id)

    def _get_owner(self, crypto_map):
        """Retourne le res.users propriétaire ou False."""
        for rec in crypto_map.values():
            if rec.owner_id:
                return rec.owner_id
        return False

    def _get_active_fields_for_user(self, user=None):
        """Champs effectifs = (prefs user ∩ admin actifs) ∪ obligatoires."""
        if user is None:
            user = self.env.user
        Config = self.env['encrypted.field.config']
        admin_active = set(Config.get_active_fields())
        mandatory = set(Config.get_mandatory_fields())

        Pref = self.env['user.encrypted.field.pref'].sudo()
        prefs = Pref.search([('user_id', '=', user.id)])
        if prefs:
            user_enabled = {p.field_name for p in prefs if p.enabled}
        else:
            user_enabled = admin_active

        return list((user_enabled & admin_active) | mandatory)

    def _build_name_display_hint(self, full_name: str) -> str:
        """
        Génère la forme abrégée du nom pour affichage public (sans déchiffrement).

        Avec display_name_chars=4 et nom "Dupont Jean-Pierre" :
          → "Dupo. J. P."
        Avec display_name_chars=1 (défaut, initiales) :
          → "D. J. P."
        """
        n = self._get_display_name_chars()
        parts = full_name.strip().replace('-', ' ').split()
        result = []
        for i, part in enumerate(parts):
            if not part:
                continue
            if i == 0:
                # Premier segment (nom de famille) : n premiers caractères
                shown = part[:n].capitalize()
                if len(part) > n:
                    shown += '.'
            else:
                # Autres segments (prénoms) : initiale uniquement
                shown = part[0].upper() + '.'
            result.append(shown)
        return ' '.join(result) or full_name

    # ── Computed fields ───────────────────────────────────────────────────────
    def _compute_has_encrypted_data(self):
        CryptoData = self.env['partner.crypto.data']
        for rec in self:
            rec.has_encrypted_data = bool(
                CryptoData.search([('partner_id', '=', rec.id)], limit=1)
            )

    @api.depends('session_password', *FIELD_NAMES)
    def _compute_display_fields(self):
        for rec in self:
            crypto_map = rec._get_crypto_map()
            owner = rec._get_owner(crypto_map)

            for field in FIELD_NAMES:
                native_val = getattr(rec, field, False) or ''
                crypto_rec = crypto_map.get(field)
                display_field = f'{field}_display'

                # Pas de données chiffrées → valeur native directement
                if not crypto_rec:
                    setattr(rec, display_field, native_val)
                    continue

                # Enregistrement chiffré sans propriétaire identifiable → native
                if not owner:
                    setattr(rec, display_field, native_val)
                    continue

                is_owner = (owner == self.env.user)

                if not is_owner:
                    # Autre utilisateur : cadenas + aperçu (initiales pour le nom)
                    if field == 'name':
                        setattr(rec, display_field,
                                f'🔒 {native_val}' if native_val else '🔒')
                    else:
                        setattr(rec, display_field, _FIELD_MASK_OTHER.get(field, '🔒'))
                    continue

                # Propriétaire du chiffrement
                if rec.session_password:
                    try:
                        decrypted = owner.decrypt_with_password(
                            crypto_rec.value_enc, rec.session_password)
                        setattr(rec, display_field, decrypted)
                    except Exception:
                        setattr(rec, display_field, '⚠️ Mot de passe incorrect')
                else:
                    if field == 'name':
                        # Pour le nom : l'aperçu est stocké directement dans rec.name
                        setattr(rec, display_field, native_val or '🔒')
                    else:
                        setattr(rec, display_field,
                                _FIELD_MASK_OWNER.get(field, '🔒'))

    @api.onchange('session_password')
    def _onchange_session_password(self):
        """Force le recalcul des champs d'affichage côté client."""
        # Les champs dépendants se recalculent automatiquement via @api.depends,
        # mais l'onchange garantit le déclenchement immédiat dans le formulaire.
        pass

    # ── Inverse functions ─────────────────────────────────────────────────────
    def _inverse_display(self, field_name: str):
        """
        Inverse générique pour les champs *_display.
        Si la valeur saisie n'est pas un masque, écrit dans le champ natif
        (qui sera chiffré par notre override de write()).
        """
        for rec in self:
            if rec.env.context.get('_crypto_inverse_running'):
                continue
            val = getattr(rec, f'{field_name}_display', '') or ''
            # Ignorer les valeurs-masques (cadenas, erreur, redacted)
            if any(val.startswith(p) for p in _LOCKED_PREFIXES) or not val.strip():
                continue
            try:
                rec.with_context(_crypto_inverse_running=True).write({field_name: val})
            except Exception as e:
                _logger.warning(
                    '[os_contact_encrypted] Inverse %s_display : %s', field_name, e)

    def _inverse_phone_display(self):   self._inverse_display('phone')
    def _inverse_mobile_display(self):  self._inverse_display('mobile')
    def _inverse_email_display(self):   self._inverse_display('email')
    def _inverse_name_display(self):    self._inverse_display('name')
    def _inverse_street_display(self):  self._inverse_display('street')
    def _inverse_vat_display(self):     self._inverse_display('vat')
    def _inverse_website_display(self): self._inverse_display('website')
    def _inverse_comment_display(self): self._inverse_display('comment')

    # ── Tokens HMAC (recherche semi-aveugle) ──────────────────────────────────
    @api.model
    def _get_blind_search_key(self):
        ICP = self.env['ir.config_parameter'].sudo()
        key = ICP.get_param('os_contact_encrypted.blind_search_key')
        if not key:
            import secrets
            key = secrets.token_hex(32)
            ICP.set_param('os_contact_encrypted.blind_search_key', key)
        return key.encode('utf-8')

    def _build_name_tokens(self, full_name: str) -> str:
        """
        Génère les tokens HMAC pour la recherche semi-aveugle sur le nom.

        Pour "Dupont Jean-Pierre" avec min_prefix=4 :
          - Mots complets   : hmac("dupont"), hmac("jean"), hmac("pierre")
          - Initiales        : hmac("d"), hmac("j"), hmac("p")
          - Préfixes ≥ min   : hmac("dupo"), hmac("dupon"), hmac("dupont"),
                               hmac("jean"), hmac("pier"), hmac("pierr"), hmac("pierre")
        Les tokens sont stockés en espace-séparés dans partner.crypto.data.token.
        """
        key = self._get_blind_search_key()
        min_len = self._get_min_search_prefix_len()
        tokens = set()
        parts = full_name.lower().replace('-', ' ').split()

        def tok(text: str) -> str:
            return hmac.new(key, text.encode('utf-8'), hashlib.sha256).hexdigest()[:BLIND_TOKEN_LEN]

        for part in parts:
            if not part:
                continue
            tokens.add(tok(part))        # mot complet
            tokens.add(tok(part[0]))     # initiale (toujours indexée)
            for length in range(min_len, len(part)):   # préfixes ≥ min_len (le mot complet déjà ajouté)
                tokens.add(tok(part[:length]))

        return ' '.join(sorted(tokens))

    def _blind_token(self, query: str) -> str | None:
        """Retourne le token HMAC pour une chaîne de recherche."""
        q = query.strip().lower()
        if not q:
            return None
        key = self._get_blind_search_key()
        return hmac.new(key, q.encode('utf-8'), hashlib.sha256).hexdigest()[:BLIND_TOKEN_LEN]

    # ── Surcharge name_search ─────────────────────────────────────────────────
    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """
        Recherche hybride : noms natifs (Odoo) + noms chiffrés (tokens HMAC).

        La recherche chiffrée fonctionne par intersection :
          - Chaque mot de la requête génère un token.
          - On cherche les contacts dont le champ token contient TOUS les tokens
            (opérateur AND implicite dans le domaine Odoo).
          - Seuls les mots d'au moins min_prefix_len caractères sont tokenisés,
            sauf les initiales (1 caractère) toujours acceptées.

        Exemple avec min_prefix=4 : "Dupo J" →
          tokens : hmac("dupo") AND hmac("j") → trouve "Dupont Jean"
        """
        if name and operator in ('ilike', 'like', '=', '=ilike', '=like'):
            min_len = self._get_min_search_prefix_len()
            parts = name.strip().lower().replace('-', ' ').split()

            # Ne conserver que les parties exploitables : ≥ min_len ou initiale (len=1)
            valid_parts = [p for p in parts if len(p) >= min_len or len(p) == 1]

            if valid_parts:
                tokens = [t for t in (self._blind_token(p) for p in valid_parts) if t]
                if tokens:
                    CryptoData = self.env['partner.crypto.data']
                    # Domaine AND : partner.name doit contenir TOUS les tokens
                    token_domain = [('field_name', '=', 'name')]
                    for token in tokens:
                        token_domain.append(('token', 'ilike', token))
                    crypto_recs = CryptoData.search(token_domain, limit=limit * 2)
                    encrypted_ids = [r.partner_id.id for r in crypto_recs]
                else:
                    encrypted_ids = []
            else:
                encrypted_ids = []

            native_ids = super()._name_search(
                name=name, domain=domain, operator=operator,
                limit=limit, order=order,
            )
            # Fusion sans doublon, natifs en premier
            seen, result = set(), []
            for id_ in list(native_ids) + encrypted_ids:
                if id_ not in seen:
                    seen.add(id_)
                    result.append(id_)
            return result[:limit]

        return super()._name_search(
            name=name, domain=domain, operator=operator,
            limit=limit, order=order,
        )

    # ── Chiffrement à la création ─────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        user = self.env.user
        if not user.rsa_public_key:
            return records

        active_fields = self._get_active_fields_for_user(user)
        CryptoData = self.env['partner.crypto.data'].sudo()

        for rec, vals in zip(records, vals_list):
            has_sensitive = any(vals.get(f) for f in active_fields)
            if not has_sensitive:
                continue

            raw_name = vals.get('name', '')

            for field in active_fields:
                value = vals.get(field) or getattr(rec, field, False)
                if not value:
                    continue
                try:
                    value_enc = user.encrypt_for_user(str(value))
                    if field == 'name':
                        token = self._build_name_tokens(raw_name)
                    else:
                        token = self._blind_token(str(value))

                    CryptoData.upsert(
                        partner_id=rec.id,
                        field_name=field,
                        value_enc=value_enc,
                        token=token,
                        owner_id=user.id,
                    )
                    # Remplacer la valeur native par l'aperçu configurable
                    if field == 'name' and raw_name:
                        rec.sudo().write({
                            'name': self._build_name_display_hint(raw_name)
                        })
                    else:
                        rec.sudo().write({field: False})
                except Exception as e:
                    _logger.warning(
                        '[os_contact_encrypted] Chiffrement create (%s): %s', field, e)

        return records

    def write(self, vals):
        # Garder le contexte inverse pour éviter la récursion
        if self.env.context.get('_crypto_inverse_running'):
            return super().write(vals)

        user = self.env.user
        CryptoData = self.env['partner.crypto.data'].sudo()

        for rec in self:
            crypto_map = rec._get_crypto_map()
            owner = rec._get_owner(crypto_map)

            # Blocage si un non-propriétaire tente de modifier un champ chiffré
            if owner and owner != user:
                active = rec._get_active_fields_for_user(owner)
                blocked = [f for f in active if f in vals and crypto_map.get(f)]
                if blocked:
                    raise exceptions.AccessError(
                        f'Données chiffrées appartenant à {owner.name} — modification interdite.'
                    )

        result = super().write(vals)

        if not user.rsa_public_key:
            return result

        active_fields = self._get_active_fields_for_user(user)

        for rec in self:
            raw_name = vals.get('name')
            for field in active_fields:
                value = vals.get(field)
                if not value:
                    continue
                try:
                    value_enc = user.encrypt_for_user(str(value))
                    if field == 'name':
                        token = self._build_name_tokens(raw_name)
                    else:
                        token = self._blind_token(str(value))

                    CryptoData.upsert(
                        partner_id=rec.id,
                        field_name=field,
                        value_enc=value_enc,
                        token=token,
                        owner_id=user.id,
                    )
                    if field == 'name' and raw_name:
                        rec.sudo().write({
                            'name': self._build_name_display_hint(raw_name)
                        })
                    else:
                        rec.sudo().write({field: False})
                except Exception as e:
                    _logger.warning(
                        '[os_contact_encrypted] Chiffrement write (%s): %s', field, e)

        return result

from odoo import models, fields, api, exceptions
from odoo.addons.os_contact_encrypted.models.encrypted_field_config import ENCRYPTABLE_FIELDS
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

FIELD_NAMES = [f for f, _ in ENCRYPTABLE_FIELDS]
BLIND_TOKEN_LEN = 16   # 64 bits — non réversible, collision négligeable


class ResPartner(models.Model):
    """
    Extension LÉGÈRE de res.partner.

    v3 — architecture satellite :
    - Aucune colonne chiffrée sur res.partner.
    - Toutes les valeurs chiffrées vivent dans partner.crypto.data.
    - Seuls deux champs légers sont ajoutés ici :
        · has_encrypted_data  (Boolean computed, store=False)
        · session_password    (transient, store=False)
    - Les champs *_display (computed, store=False) assurent la rétrocompat
      des vues sans toucher aux colonnes natives.
    - Zéro migration SQL nécessaire lors des mises à jour.
    """
    _inherit = 'res.partner'

    # ── Champs ajoutés sur res.partner (store=False uniquement) ───────────────
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

    # ── Champs d'affichage (computed, store=False) ────────────────────────────
    phone_display   = fields.Char(string='Téléphone',  compute='_compute_display_fields', store=False)
    mobile_display  = fields.Char(string='Mobile',     compute='_compute_display_fields', store=False)
    email_display   = fields.Char(string='Email',      compute='_compute_display_fields', store=False)
    name_display    = fields.Char(string='Nom',        compute='_compute_display_fields', store=False)
    street_display  = fields.Char(string='Adresse',    compute='_compute_display_fields', store=False)
    vat_display     = fields.Char(string='N° fiscal',  compute='_compute_display_fields', store=False)
    website_display = fields.Char(string='Site web',   compute='_compute_display_fields', store=False)
    comment_display = fields.Char(string='Notes',      compute='_compute_display_fields', store=False)

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
                native_val = getattr(rec, field, False)
                crypto_rec = crypto_map.get(field)

                if not crypto_rec:
                    # Pas de données chiffrées → valeur native
                    setattr(rec, f'{field}_display', native_val)
                    continue

                if not owner:
                    setattr(rec, f'{field}_display', native_val)
                    continue

                if owner != self.env.user:
                    setattr(rec, f'{field}_display', '████████')
                elif rec.session_password:
                    try:
                        decrypted = owner.decrypt_with_password(
                            crypto_rec.value_enc, rec.session_password
                        )
                        setattr(rec, f'{field}_display', decrypted)
                    except Exception:
                        setattr(rec, f'{field}_display', '⚠️ Mot de passe incorrect')
                else:
                    setattr(rec, f'{field}_display', '🔒 (saisissez votre mot de passe)')

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
        Génère des tokens HMAC pour la recherche semi-aveugle.
        Pour "Dupont Jean-Pierre" :
          - mot complet : hmac("dupont"), hmac("jean"), hmac("pierre")
          - initiales   : hmac("d"), hmac("j"), hmac("p")
          - préfixes 3+ : hmac("dup"), hmac("dupo"), hmac("dupon")…
        """
        key = self._get_blind_search_key()
        tokens = set()
        parts = full_name.lower().replace('-', ' ').split()

        def tok(text):
            return hmac.new(key, text.encode('utf-8'), hashlib.sha256).hexdigest()[:BLIND_TOKEN_LEN]

        for part in parts:
            tokens.add(tok(part))
            tokens.add(tok(part[0]))
            for length in range(3, len(part) + 1):
                tokens.add(tok(part[:length]))

        return ' '.join(sorted(tokens))

    def _blind_token(self, query: str) -> str | None:
        q = query.strip().lower()
        if not q:
            return None
        key = self._get_blind_search_key()
        return hmac.new(key, q.encode('utf-8'), hashlib.sha256).hexdigest()[:BLIND_TOKEN_LEN]

    # ── Surcharge name_search ─────────────────────────────────────────────────
    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        if name and operator in ('ilike', 'like', '=', '=ilike', '=like'):
            token = self._blind_token(name)
            if token:
                encrypted_ids = self.env['partner.crypto.data'].search_by_token(token, limit=limit)
                native_ids = super()._name_search(
                    name=name, domain=domain, operator=operator, limit=limit, order=order
                )
                seen, result = set(), []
                for id_ in list(native_ids) + encrypted_ids:
                    if id_ not in seen:
                        seen.add(id_)
                        result.append(id_)
                return result[:limit]

        return super()._name_search(
            name=name, domain=domain, operator=operator, limit=limit, order=order
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
                    token = self._blind_token(str(value)) if field == 'name' else None

                    CryptoData.upsert(
                        partner_id=rec.id,
                        field_name=field,
                        value_enc=value_enc,
                        token=self._build_name_tokens(raw_name) if field == 'name' else token,
                        owner_id=user.id,
                    )
                    # Effacer la valeur native (remplacée par les initiales pour le nom)
                    if field == 'name' and raw_name:
                        parts = raw_name.replace('-', ' ').split()
                        rec.sudo().write({
                            'name': ''.join(p[0].upper() + '.' for p in parts if p)
                        })
                    else:
                        rec.sudo().write({field: False})
                except Exception as e:
                    _logger.warning(
                        '[os_contact_encrypted] Chiffrement create (%s): %s', field, e
                    )

        return records

    def write(self, vals):
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
                    token = self._build_name_tokens(raw_name) if field == 'name' else self._blind_token(str(value))

                    CryptoData.upsert(
                        partner_id=rec.id,
                        field_name=field,
                        value_enc=value_enc,
                        token=token,
                        owner_id=user.id,
                    )
                    if field == 'name' and raw_name:
                        parts = raw_name.replace('-', ' ').split()
                        rec.sudo().write({
                            'name': ''.join(p[0].upper() + '.' for p in parts if p)
                        })
                    else:
                        rec.sudo().write({field: False})
                except Exception as e:
                    _logger.warning(
                        '[os_contact_encrypted] Chiffrement write (%s): %s', field, e
                    )

        return result

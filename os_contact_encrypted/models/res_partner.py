from odoo import models, fields, api, exceptions
from odoo.addons.os_contact_encrypted.models.encrypted_field_config import ENCRYPTABLE_FIELDS
import hashlib
import hmac
import logging

_logger = logging.getLogger(__name__)

FIELD_NAMES = [f for f, _ in ENCRYPTABLE_FIELDS]
BLIND_TOKEN_LEN = 16   # 64 bits

# Masques visuels pour le propriétaire sans MDP saisi
_MASK_OWNER = {
    'phone':   '🔒 ── ── ── ──',
    'mobile':  '🔒 ── ── ── ──',
    'email':   '🔒 ────@────.──',
    'name':    None,              # cas spécial : aperçu stocké dans rec.name
    'street':  '🔒 ─────────────',
    'vat':     '🔒 ─────────────',
    'website': '🔒 ────────────',
    'comment': '🔒 ─────────────',
}

# Préfixes de masque → ne pas rechiffrer ces valeurs
_MASK_PREFIXES = ('🔒', '⚠️', '████')

# Contexte interne : efface la colonne native SANS repasser dans la logique de chiffrement
_CTX_CLEAR = '_crypto_write_clear_native'


class ResPartner(models.Model):
    """
    Extension LÉGÈRE de res.partner — v4 (architecture satellite).

    Principe du chiffrement dans create/write :
    ────────────────────────────────────────────
    Les champs sensibles sont EXTRAITS de vals AVANT super(), de sorte que
    la valeur en clair ne transite jamais dans la table res.partner.
    Après chiffrement dans partner.crypto.data, la colonne native est
    effacée/renseignée via un write() portant le contexte _CTX_CLEAR,
    qui bypasse toute logique de chiffrement (pas de récursion).

    Recherche ZK multi-mots :
    ──────────────────────────
    "Dupo J"  →  tokens [hmac("dupo"), hmac("j")]
              →  domaine AND dans partner.crypto.data.token
              →  trouve "Dupont Jean"
    """
    _inherit = 'res.partner'

    # ── Champs transients ─────────────────────────────────────────────────────
    has_encrypted_data = fields.Boolean(
        string='Données chiffrées',
        compute='_compute_has_encrypted_data',
        store=False,
    )
    session_password = fields.Char(
        string='Mot de passe de déchiffrement',
        store=False,
        default=False,
        # NE PAS mettre password=True ici : cela empêche Odoo de renvoyer
        # la valeur au client, rendant le champ inutilisable comme déclencheur.
        # Le masquage visuel est assuré par widget="password" dans la vue XML.
    )

    # ── Champs display avec inverse ───────────────────────────────────────────
    phone_display   = fields.Char(string='Téléphone',  compute='_compute_display_fields', inverse='_inv_phone',   store=False)
    mobile_display  = fields.Char(string='Mobile',     compute='_compute_display_fields', inverse='_inv_mobile',  store=False)
    email_display   = fields.Char(string='Email',      compute='_compute_display_fields', inverse='_inv_email',   store=False)
    name_display    = fields.Char(string='Nom',        compute='_compute_display_fields', inverse='_inv_name',    store=False)
    street_display  = fields.Char(string='Adresse',    compute='_compute_display_fields', inverse='_inv_street',  store=False)
    vat_display     = fields.Char(string='N° fiscal',  compute='_compute_display_fields', inverse='_inv_vat',     store=False)
    website_display = fields.Char(string='Site web',   compute='_compute_display_fields', inverse='_inv_website', store=False)
    comment_display = fields.Char(string='Notes',      compute='_compute_display_fields', inverse='_inv_comment', store=False)

    # ── Lecture des paramètres de configuration ───────────────────────────────
    def _cfg_int(self, key, default):
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'os_contact_encrypted.' + key, str(default)))
        except Exception:
            return default

    def _min_prefix_len(self):
        return max(2, min(self._cfg_int('min_search_prefix_len', 3), 8))

    def _display_name_chars(self):
        return max(1, min(self._cfg_int('display_name_chars', 1), 10))

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _get_crypto_map(self):
        return self.env['partner.crypto.data'].get_for_partner(self.id)

    def _get_owner(self, crypto_map):
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
        mandatory    = set(Config.get_mandatory_fields())
        Pref  = self.env['user.encrypted.field.pref'].sudo()
        prefs = Pref.search([('user_id', '=', user.id)])
        user_enabled = {p.field_name for p in prefs if p.enabled} if prefs else admin_active
        return list((user_enabled & admin_active) | mandatory)

    def _name_hint(self, full_name: str) -> str:
        """
        Forme abrégée du nom pour affichage sans déchiffrement.
        display_name_chars=4, "Dupont Jean-Pierre"  →  "Dupo. J. P."
        display_name_chars=1  (initiales par défaut) →  "D. J. P."
        """
        n = self._display_name_chars()
        parts = full_name.strip().replace('-', ' ').split()
        result = []
        for i, p in enumerate(parts):
            if not p:
                continue
            if i == 0:
                shown = p[:n].capitalize()
                if len(p) > n:
                    shown += '.'
            else:
                shown = p[0].upper() + '.'
            result.append(shown)
        return ' '.join(result) or full_name

    # ── Computed fields ───────────────────────────────────────────────────────
    def _compute_has_encrypted_data(self):
        CryptoData = self.env['partner.crypto.data']
        for rec in self:
            rec.has_encrypted_data = bool(
                CryptoData.search([('partner_id', '=', rec.id)], limit=1))

    @api.depends('session_password', *FIELD_NAMES)
    def _compute_display_fields(self):
        for rec in self:
            crypto_map = rec._get_crypto_map()
            owner = rec._get_owner(crypto_map)

            for field in FIELD_NAMES:
                native_val   = getattr(rec, field, False) or ''
                crypto_rec   = crypto_map.get(field)
                display_attr = f'{field}_display'

                if not crypto_rec:
                    # Pas de données chiffrées → valeur native
                    setattr(rec, display_attr, native_val)
                    continue

                if not owner:
                    setattr(rec, display_attr, native_val)
                    continue

                is_owner = (owner == self.env.user)

                if not is_owner:
                    if field == 'name':
                        setattr(rec, display_attr,
                                ('🔒 ' + native_val) if native_val else '🔒')
                    else:
                        setattr(rec, display_attr, '🔒')
                    continue

                # Propriétaire du chiffrement
                if rec.session_password:
                    try:
                        decrypted = owner.decrypt_with_password(
                            crypto_rec.value_enc, rec.session_password)
                        setattr(rec, display_attr, decrypted)
                    except Exception:
                        setattr(rec, display_attr, '⚠️ Mot de passe incorrect')
                else:
                    if field == 'name':
                        # L'aperçu (hint) est stocké dans rec.name
                        setattr(rec, display_attr, native_val or '🔒')
                    else:
                        setattr(rec, display_attr, _MASK_OWNER.get(field, '🔒'))

    @api.onchange('session_password')
    def _onchange_session_password(self):
        """
        Force le recalcul ET l'envoi des champs display dans la réponse onchange.

        Odoo 17 : un onchange avec corps vide déclenche le RPC côté client mais
        n'inclut dans sa réponse que les champs EXPLICITEMENT modifiés dans la
        méthode. Les @api.depends ne sont pas réévalués automatiquement dans ce
        contexte. L'appel explicite ci-dessous force :
          1. L'évaluation de _compute_display_fields avec le mot de passe disponible.
          2. L'inclusion de tous les *_display dans la réponse onchange → mise à jour
             immédiate du formulaire avec les valeurs déchiffrées.
        Le mot de passe reste purement transient (store=False, jamais sauvegardé).
        """
        self._compute_display_fields()

    # ── Inverse functions ─────────────────────────────────────────────────────
    def _inv(self, field_name):
        """
        Inverse générique.
        Si la valeur saisie n'est pas un masque, on appelle write() sur le
        champ natif. write() intercepte, chiffre, et efface la colonne native.
        """
        for rec in self:
            val = getattr(rec, f'{field_name}_display', '') or ''
            if not val.strip() or any(val.startswith(p) for p in _MASK_PREFIXES):
                continue
            rec.write({field_name: val})

    def _inv_phone(self):    self._inv('phone')
    def _inv_mobile(self):   self._inv('mobile')
    def _inv_email(self):    self._inv('email')
    def _inv_name(self):     self._inv('name')
    def _inv_street(self):   self._inv('street')
    def _inv_vat(self):      self._inv('vat')
    def _inv_website(self):  self._inv('website')
    def _inv_comment(self):  self._inv('comment')

    # ── Clé HMAC + tokens ────────────────────────────────────────────────────
    def _search_key(self):
        ICP = self.env['ir.config_parameter'].sudo()
        key = ICP.get_param('os_contact_encrypted.blind_search_key')
        if not key:
            import secrets
            key = secrets.token_hex(32)
            ICP.set_param('os_contact_encrypted.blind_search_key', key)
        return key.encode('utf-8')

    def _tok(self, text: str) -> str:
        return hmac.new(self._search_key(),
                        text.encode('utf-8'),
                        hashlib.sha256).hexdigest()[:BLIND_TOKEN_LEN]

    def _build_name_tokens(self, full_name: str) -> str:
        """
        Génère l'ensemble des tokens pour l'indexation ZK du nom.
        min_prefix=4, "Dupont Jean-Pierre" :
          → hmac("dupont") hmac("jean") hmac("pierre")   (mots complets)
          → hmac("d") hmac("j") hmac("p")                (initiales)
          → hmac("dupo") hmac("dupon")                   (préfixes ≥4)
          → hmac("jean")                                  (déjà ajouté)
          → hmac("pier") hmac("pierr")                   (préfixes ≥4)
        """
        min_len = self._min_prefix_len()
        tokens  = set()
        parts   = full_name.lower().replace('-', ' ').split()
        for part in parts:
            if not part:
                continue
            tokens.add(self._tok(part))
            tokens.add(self._tok(part[0]))
            for length in range(min_len, len(part)):
                tokens.add(self._tok(part[:length]))
        return ' '.join(sorted(tokens))

    # ── Recherche hybride ─────────────────────────────────────────────────────
    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        if name and operator in ('ilike', 'like', '=', '=ilike', '=like'):
            min_len = self._min_prefix_len()
            parts   = name.strip().lower().replace('-', ' ').split()
            valid   = [p for p in parts if len(p) >= min_len or len(p) == 1]
            tokens  = [self._tok(p) for p in valid if p]

            encrypted_ids = []
            if tokens:
                CryptoData = self.env['partner.crypto.data']
                dom = [('field_name', '=', 'name')]
                for tok in tokens:
                    dom.append(('token', 'ilike', tok))
                recs = CryptoData.search(dom, limit=limit * 2)
                encrypted_ids = [r.partner_id.id for r in recs]

            native_ids = list(super()._name_search(
                name=name, domain=domain, operator=operator,
                limit=limit, order=order))

            seen, result = set(), []
            for pid in native_ids + encrypted_ids:
                if pid not in seen:
                    seen.add(pid)
                    result.append(pid)
            return result[:limit]

        return super()._name_search(
            name=name, domain=domain, operator=operator, limit=limit, order=order)

    # ── Chiffrement d'un enregistrement ──────────────────────────────────────
    def _do_encrypt(self, rec, sensitive: dict, user):
        """
        Chiffre chaque champ de `sensitive`, upsert dans partner.crypto.data,
        puis écrit le hint (nom) ou False (autres) dans la colonne native
        via un write() portant _CTX_CLEAR — qui ne repasse PAS dans cette méthode.
        """
        CryptoData = self.env['partner.crypto.data'].sudo()

        for field, value in sensitive.items():
            if not value:
                continue
            try:
                value_str = str(value)
                value_enc = user.encrypt_for_user(value_str)

                if field == 'name':
                    token = self._build_name_tokens(value_str)
                    native_write = {'name': self._name_hint(value_str)}
                else:
                    token = self._tok(value_str)
                    native_write = {field: False}

                CryptoData.upsert(
                    partner_id=rec.id,
                    field_name=field,
                    value_enc=value_enc,
                    token=token,
                    owner_id=user.id,
                )
                # Effacement/remplacement de la colonne native — bypass chiffrement
                rec.with_context(**{_CTX_CLEAR: True}).sudo().write(native_write)

            except Exception as e:
                _logger.warning(
                    '[os_contact_encrypted] _do_encrypt %s (partner %s): %s',
                    field, rec.id, e)

    # ── create ────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """
        Les champs sensibles sont retirés de vals_list avant super().create()
        pour ne jamais persister en clair en base.
        """
        user = self.env.user

        if not user.rsa_public_key:
            return super().create(vals_list)

        active_fields = self._get_active_fields_for_user(user)

        # Séparer les données sensibles des données ordinaires
        # CAS PARTICULIER 'name' : champ NOT NULL dans res.partner.
        # On met le hint (N premiers chars) dans clean pour satisfaire la contrainte,
        # de sorte que le nom complet ne transite JAMAIS en clair dans la base.
        sensitive_per = []
        clean_list    = []
        for vals in vals_list:
            sensitive = {}
            clean     = {}
            for k, v in vals.items():
                if k in active_fields and v:
                    sensitive[k] = v
                    if k == 'name':
                        # Placeholder hint dans clean : satisfait NOT NULL sans exposer le nom
                        clean['name'] = self._name_hint(str(v))
                    # Les autres champs sensibles sont absents de clean (colonnes nullable)
                else:
                    clean[k] = v
            sensitive_per.append(sensitive)
            clean_list.append(clean)

        records = super().create(clean_list)

        for rec, sensitive in zip(records, sensitive_per):
            if sensitive:
                self._do_encrypt(rec, sensitive, user)

        return records

    # ── write ─────────────────────────────────────────────────────────────────
    def write(self, vals):
        # ── Écriture interne (effacement colonne native) → passe directement ──
        if self.env.context.get(_CTX_CLEAR):
            return super().write(vals)

        user = self.env.user

        # ── Contrôle d'accès (données d'un autre utilisateur) ─────────────────
        for rec in self:
            crypto_map = rec._get_crypto_map()
            owner = rec._get_owner(crypto_map)
            if owner and owner != user:
                active  = rec._get_active_fields_for_user(owner)
                blocked = [f for f in active if f in vals and crypto_map.get(f)]
                if blocked:
                    raise exceptions.AccessError(
                        f'Données chiffrées appartenant à {owner.name} — modification interdite.')

        if not user.rsa_public_key:
            return super().write(vals)

        active_fields = self._get_active_fields_for_user(user)

        # ── Extraire les champs sensibles AVANT super().write() ───────────────
        # session_password est exclu de tout traitement : purement transient,
        # il ne doit ni être chiffré, ni être écrit en DB.
        vals_without_session = {k: v for k, v in vals.items() if k != 'session_password'}
        sensitive = {k: v for k, v in vals_without_session.items() if k in active_fields and v}
        clean     = {k: v for k, v in vals_without_session.items() if k not in sensitive}

        # ── Écrire les champs non-sensibles normalement ───────────────────────
        result = super().write(clean) if clean else True

        # ── Chiffrer et stocker ───────────────────────────────────────────────
        if sensitive:
            for rec in self:
                self._do_encrypt(rec, sensitive, user)

        return result

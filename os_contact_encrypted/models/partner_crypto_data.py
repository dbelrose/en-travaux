from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class PartnerCryptoData(models.Model):
    """
    Table satellite : stocke TOUTES les données chiffrées et les métadonnées
    de chiffrement pour un contact, sans toucher à res.partner.

    Une ligne par (partner, field_name) — design EAV ciblé.
    Zero colonne ajoutée sur res.partner → aucune migration SQL lors des
    mises à jour du module.

    Colonnes :
        partner_id   FK vers res.partner (cascade delete)
        company_id   société courante (multi-société natif)
        field_name   nom du champ Odoo (ex. 'phone', 'email', 'name')
        value_enc    blob base64 RSA-OAEP chiffré
        token        HMAC-SHA256 tronqué pour la recherche semi-aveugle
        owner_id     utilisateur propriétaire du chiffrement
    """
    _name = 'partner.crypto.data'
    _description = 'Données chiffrées des contacts (table satellite)'
    _order = 'partner_id, field_name'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    field_name = fields.Char(
        string='Champ',
        required=True,
        index=True,
    )
    value_enc = fields.Text(
        string='Valeur chiffrée (base64)',
        copy=False,
    )
    token = fields.Char(
        string='Token de recherche (HMAC)',
        index=True,
        copy=False,
        help='Token HMAC-SHA256 tronqué pour la recherche semi-aveugle.',
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Propriétaire',
        required=True,
        ondelete='restrict',
        index=True,
    )

    _sql_constraints = [
        (
            'unique_partner_field_company',
            'UNIQUE(partner_id, field_name, company_id)',
            'Un seul enregistrement chiffré par champ, contact et société.',
        ),
    ]

    # ── API interne ────────────────────────────────────────────────────────────

    @api.model
    def get_for_partner(self, partner_id, field_names=None):
        """
        Retourne un dict {field_name: record} pour un contact donné.
        Filtré sur la société courante.
        """
        domain = [
            ('partner_id', '=', partner_id),
            ('company_id', '=', self.env.company.id),
        ]
        if field_names:
            domain.append(('field_name', 'in', field_names))
        records = self.search(domain)
        return {r.field_name: r for r in records}

    @api.model
    def upsert(self, partner_id, field_name, value_enc, token, owner_id):
        """
        Crée ou met à jour l'enregistrement pour (partner, field, company).
        Retourne le record.
        """
        existing = self.search([
            ('partner_id', '=', partner_id),
            ('field_name', '=', field_name),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        vals = {
            'value_enc': value_enc,
            'token': token,
            'owner_id': owner_id,
        }
        if existing:
            existing.write(vals)
            return existing
        vals.update({
            'partner_id': partner_id,
            'field_name': field_name,
            'company_id': self.env.company.id,
        })
        return self.create(vals)

    @api.model
    def search_by_token(self, token, limit=100):
        """
        Recherche semi-aveugle : retourne les partner_ids dont au moins
        un champ contient ce token HMAC.
        """
        records = self.search([('token', 'ilike', token)], limit=limit)
        return list({r.partner_id.id for r in records})

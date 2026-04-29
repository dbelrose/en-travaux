from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

# Champs proposés à l'administrateur pour activation globale
ENCRYPTABLE_FIELDS = [
    ('phone',   'Téléphone'),
    ('mobile',  'Mobile'),
    ('email',   'Email'),
    ('name',    'Nom complet'),
    ('street',  'Adresse'),
    ('vat',     'Numéro fiscal / Sécurité sociale'),
    ('website', 'Site web'),
    ('comment', 'Notes internes'),
]


class EncryptedFieldConfig(models.Model):
    """
    Registre global (admin) des champs de res.partner pouvant être chiffrés.
    Chaque enregistrement = un champ autorisé pour le chiffrement.
    L'administrateur (groupe crypto_admin) active/désactive les champs.
    Les utilisateurs ne peuvent activer que des champs autorisés ici.
    """
    _name = 'encrypted.field.config'
    _description = 'Configuration des champs chiffrés (admin)'
    _order = 'field_name'

    field_name = fields.Selection(
        selection=ENCRYPTABLE_FIELDS,
        string='Champ à chiffrer',
        required=True,
    )
    label = fields.Char(
        string='Libellé affiché',
        compute='_compute_label',
        store=True,
    )
    active = fields.Boolean(default=True, string='Actif')
    # Si True, l'utilisateur ne peut PAS désactiver ce champ dans ses préférences
    mandatory = fields.Boolean(
        default=False,
        string='Obligatoire',
        help='Si coché, tous les utilisateurs chiffrent ce champ sans pouvoir le désactiver.',
    )
    note = fields.Char(string='Note', help='Information complémentaire.')

    _sql_constraints = [
        ('unique_field', 'UNIQUE(field_name)', 'Ce champ est déjà configuré.'),
    ]

    @api.depends('field_name')
    def _compute_label(self):
        mapping = dict(ENCRYPTABLE_FIELDS)
        for rec in self:
            rec.label = mapping.get(rec.field_name, rec.field_name)

    @api.model
    def get_active_fields(self):
        """Liste des noms de champs activés globalement par l'admin."""
        return self.search([('active', '=', True)]).mapped('field_name')

    @api.model
    def get_mandatory_fields(self):
        """Liste des champs que l'utilisateur ne peut pas désactiver."""
        return self.search([('active', '=', True), ('mandatory', '=', True)]).mapped('field_name')


class UserEncryptedFieldPref(models.Model):
    """
    Préférences utilisateur : quels champs (parmi ceux autorisés par l'admin)
    cet utilisateur veut effectivement chiffrer.
    """
    _name = 'user.encrypted.field.pref'
    _description = 'Préférences de chiffrement par utilisateur'
    _order = 'field_name'

    user_id = fields.Many2one('res.users', string='Utilisateur', required=True, ondelete='cascade')
    field_name = fields.Selection(
        selection=ENCRYPTABLE_FIELDS,
        string='Champ',
        required=True,
    )
    enabled = fields.Boolean(default=True, string='Chiffrer ce champ')

    _sql_constraints = [
        ('unique_user_field', 'UNIQUE(user_id, field_name)', 'Préférence déjà enregistrée.'),
    ]

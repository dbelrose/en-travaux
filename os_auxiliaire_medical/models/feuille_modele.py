from odoo import models, fields, api


class CpsFeuilleModele(models.Model):
    _name = 'cps.feuille.soins.modele'
    _description = 'Modèle de feuille de soins (template réutilisable)'
    _order = 'profession, name'

    name = fields.Char(string='Nom du modèle', required=True)

    # Filtrage par profession : seuls les modèles compatibles sont proposés
    profession = fields.Selection([
        ('kinesitherapeute', 'Masseur-kinésithérapeute'),
        ('orthophoniste', 'Orthophoniste'),
        ('orthoptiste', 'Orthoptiste'),
        ('pedicure', 'Pédicure-Podologue'),
        ('infirmier', 'Infirmier(e)'),
        ('autre', 'Autre'),
    ], string='Profession', required=True,
       help='Seuls les praticiens de cette profession verront ce modèle proposé.')

    # Paramètres repris sur la feuille lors de l'application
    condition = fields.Selection([
        ('maladie', 'Maladie (défaut)'),
        ('longue_maladie', 'Longue Maladie'),
        ('at_mp', 'AT/MP'),
        ('maternite', 'Maternité'),
        ('urgence', 'Urgence'),
        ('autre', 'Autres dérogations'),
    ], string='Condition par défaut', default='maladie')
    taux_remboursement = fields.Float(string='Taux de remboursement (%)', default=70.0)

    ligne_ids = fields.One2many(
        'cps.feuille.soins.modele.ligne', 'modele_id', string='Lignes d\'actes',
    )
    nb_lignes = fields.Integer(compute='_compute_nb_lignes', string='Nb actes')

    # ── Multi-company ───────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.depends('ligne_ids')
    def _compute_nb_lignes(self):
        for rec in self:
            rec.nb_lignes = len(rec.ligne_ids)


class CpsFeuilleModeleLigne(models.Model):
    _name = 'cps.feuille.soins.modele.ligne'
    _description = 'Ligne d\'acte d\'un modèle de feuille'
    _order = 'sequence, id'

    modele_id = fields.Many2one(
        'cps.feuille.soins.modele', required=True, ondelete='cascade',
    )
    sequence = fields.Integer(default=10)

    acte_type_id = fields.Many2one(
        'cps.acte.type', string='Type d\'acte', required=True, ondelete='restrict',
    )
    # Repris depuis acte_type_id, modifiable pour personnalisation du modèle
    lettre_cle = fields.Char(string='Lettre clé', related='acte_type_id.lettre_cle', readonly=True)
    coefficient = fields.Float(string='Coefficient', digits=(6, 2))
    ifd = fields.Float(string='IFD', default=0)
    ik = fields.Float(string='IK', default=0)
    dimanche_ferie = fields.Boolean(string='Dim./Férié')
    nuit = fields.Boolean(string='Nuit')

    @api.onchange('acte_type_id')
    def _onchange_acte_type_id(self):
        if self.acte_type_id and not self.coefficient:
            self.coefficient = self.acte_type_id.coefficient_defaut

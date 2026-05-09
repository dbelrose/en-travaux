from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CpsBordereauModele(models.Model):
    """
    Gabarit de présentation pour les bordereaux de facturation CPS.
    Permet de personnaliser en-tête, pied de page, colonnes affichées
    et textes d'accompagnement par société.
    """
    _name = 'cps.bordereau.modele'
    _description = 'Modèle de document – Bordereau CPS'
    _order = 'sequence, name'
    _rec_name = 'name'

    name     = fields.Char(string='Nom du modèle', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    active   = fields.Boolean(default=True)
    is_default = fields.Boolean(
        string='Modèle par défaut',
        help='Pré-sélectionné à la création d\'un nouveau bordereau.',
    )

    company_id = fields.Many2one(
        'res.company', string='Société',
        help='Laisser vide pour rendre ce modèle disponible à toutes les sociétés.',
    )

    # ── Personnalisation visuelle ─────────────────────────────────────────────
    entete_texte = fields.Text(
        string='Texte d\'en-tête',
        help='Texte affiché en haut du bordereau (informations cabinet, RPPS, etc.).',
        default='BORDEREAU DE FACTURATION MENSUEL\nCaisse de Prévoyance Sociale – Polynésie française',
    )
    pied_page_texte = fields.Text(
        string='Texte de pied de page',
        help='Texte affiché en bas du bordereau (coordonnées, signature, etc.).',
    )
    mention_complementaire = fields.Text(
        string='Mention complémentaire',
        help='Mention légale ou informative à insérer après le tableau de facturation.',
    )

    # ── Colonnes affichées ────────────────────────────────────────────────────
    afficher_dn           = fields.Boolean(string='Afficher N° DN',          default=True)
    afficher_date_naissance = fields.Boolean(string='Afficher date de naissance', default=False)
    afficher_date_debut   = fields.Boolean(string='Afficher date début soins', default=True)
    afficher_date_fin     = fields.Boolean(string='Afficher date fin soins',   default=True)
    afficher_nb_actes     = fields.Boolean(string='Afficher nb actes',         default=False)
    afficher_part_cps     = fields.Boolean(string='Afficher part CPS',         default=True)
    afficher_part_patient = fields.Boolean(string='Afficher part patient',     default=True)
    afficher_total_ligne  = fields.Boolean(string='Afficher total par ligne',  default=False)

    # ── Style ─────────────────────────────────────────────────────────────────
    couleur_principale = fields.Char(
        string='Couleur principale (hex)',
        default='1F6B3A',
        help='Code hexadécimal (sans #) utilisé pour l\'en-tête et les totaux.',
    )

    notes = fields.Text(string='Notes internes')

    @api.constrains('is_default', 'company_id')
    def _check_unique_default(self):
        for rec in self:
            if rec.is_default:
                domain = [
                    ('is_default', '=', True),
                    ('id', '!=', rec.id),
                    ('company_id', '=', rec.company_id.id if rec.company_id else False),
                ]
                if self.search_count(domain) > 0:
                    raise ValidationError(_(
                        'Il ne peut y avoir qu\'un seul modèle par défaut par société.'
                    ))

    @api.model
    def get_default_modele(self, company=None):
        """Retourne le modèle par défaut pour la société courante."""
        company = company or self.env.company
        modele = self.search([
            ('is_default', '=', True),
            '|', ('company_id', '=', company.id), ('company_id', '=', False),
        ], order='company_id desc', limit=1)
        return modele

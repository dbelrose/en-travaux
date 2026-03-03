import json
from odoo import fields, models, api
from datetime import date
from odoo.exceptions import ValidationError


class PilDemande(models.Model):
    _name = 'pil.demande'
    _description = 'Description'

    name = fields.Char(string='Demande')
    user_id = fields.Many2one('res.users', string='Agent Saisie', default=lambda self: self.env.user,
                              help="Agent ayant traitée la demande")
    company_id = fields.Many2one('res.company', index=True, default=lambda self: self.env.company.id)
    ref_lieu_id = fields.Many2one('ref.lieu', help="Lieu ou se trouve le bien", delegate=True)
    lieu_commune = fields.Char(string='Commune de localisation', related='ref_lieu_id.commune')
    origine = fields.Selection(selection=[('PF', 'Polynesie'), ('HORS', 'Hors Polynesie')],
                               string="Origine du demandeur", required=True)
    ref_origine_demandeur_id = fields.Many2one('ref.lieu', string="Localisation du demandeur")
    origine_commune = fields.Char(string='commune origine', related='ref_origine_demandeur_id.commune')
    origine_ile = fields.Char(string='ile origine', related='ref_origine_demandeur_id.ile_id.name')
    origine_archipel = fields.Char(string='archipel origine', related='ref_origine_demandeur_id.archipel_id.name')
    date_demande = fields.Date(
        string='Date de demande',
        default=date.today(),  # Set the default value to today's date
        required=True,
        help="Date de depot de la demande")
    type_contact = fields.Selection(
        selection=[('presentiel', 'En Présentiel'), ('mail', 'Par Mail'), ('tel', 'Par Téléphone'),
                   ('courrier', 'Par Courrier'),
                   ('formulaire', 'Par Formulaire')], string='Type de contact', required=True)
    typeusager_id = fields.Selection(selection=[
        ('locataire', 'Locataire'), ('proprietaire', 'Propriétaire'), ('agence', 'Agence Immobiliere'),
        ('autre', 'Autre')], string="Type d'usager", required=True)
    tel = fields.Char(string='Téléphone', help="téléphone de l'usager")
    mail = fields.Char(string='Email', help="emails de l'usager")
    naturelogement_id = fields.Many2one('pil.parametrage', string='Nature du logement', index=True, required=True,
                                        help="nature du bien")
    question = fields.Text(string='Question', required=True, help='Informations demandées', index=True)
    rubrique = fields.Selection(
        selection=[('location', 'Location'), ('copropriete', 'Copropriété'), ('aideslogement', 'Aides Logement'),
                   ('autrerubrique', 'Autres')],
        string='Rubrique', required=True)
    duree_traitement = fields.Many2one('pil.parametrage', string='Durée du traitement', help="Durée du traitement")

    @api.depends('rubrique')
    def _compute_ssrubrique_id_domain(self):
        for rec in self:
            rec.ssrubrique_id_domain = json.dumps(
                [('categorie', '=', rec.rubrique)]
            )

    ssrubrique_id = fields.Many2one('pil.parametrage', string='Sous rubrique', required=True, index=True)
    ssrubrique_id_domain = fields.Char(string='ssrubrique_id_domain', compute="_compute_ssrubrique_id_domain",
                                       readonly=True, store=False, index=True)
    type_solution_ids = fields.Many2many('pil.parametrage', string='Solution adoptée')
    date_reponse = fields.Date(string='Date de réponse', Help='Date de réponse')
    reponse = fields.Boolean(string='Répondu', Help='Demande Traité ou non')
    state = fields.Selection(selection=[('encours', 'En cours'), ('traite', 'Traité')], default='encours')

    @api.constrains('date_demande')
    def _check_date_demande(self):
        for record in self:
            if record.date_demande > fields.Date.today():
                raise ValidationError("The  date demand cannot be set in the futur")
        # all records passed the test, don't return anything

    @api.constrains('date_reponse')
    def _check_date_reponse(self):
        for record in self:
            if record.date_reponse:
                if record.date_reponse > fields.Date.today():
                    raise ValidationError("The  date de reponse cannot be set in the futur")
        # all records passed the test, don't return anything

    @api.onchange('reponse')
    def _onchange_reponse(self):
        if self.reponse:
            self.state = 'traite'
        else:
            self.state = 'encours'

    @api.onchange('type_contact')
    def _onchange_type_contact(self):
        if self.type_contact == "presentiel":
            lieu = self.env["ref.lieu"].search([('name', '=', 'PAPEETE')], limit=1)
            if lieu:
                self.ref_origine_demandeur_id = lieu.id

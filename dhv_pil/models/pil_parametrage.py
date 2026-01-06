from odoo import fields, models, api

class PilParametrage (models.Model):
    _name = 'pil.parametrage'
    _description = 'Description Parametrage globale'

    name = fields.Char()
    categorie=fields.Selection(selection=[('rubrique','Rubrique'),('typecontact','Type de contact'),
        ('typeusager',"Type d'usager"),('naturebien',"Nature de logement"),('rubrique',"Rubrique"),
        ('location',"Rubrique location"),('copropriete',"Rubrique coproprieté"),('aideslogement',"Rubrique Aides Logement"),
        ('autrerubrique',"Rubrique Autres"),('solution','Solution'),('dureetraitement','Duree Traitement')],string='categorie',Help='catégorie')
    parametre=fields.Char(string='sous rubrique',Help='sous rubrique associée')

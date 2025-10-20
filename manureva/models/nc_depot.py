from odoo import fields, models


class NCDepot(models.Model):
    _name = 'manureva.nc_depot'
    _description = 'Vols autres que ceux de transport aérien public'

    aerodrome_id = fields.Many2one(
        'manureva.aerodrome',
        string='NC01',
        # string='Aérodrome source',
        help="Inscrire le Code OACI de l'aérodrome collectant les données",
        required=True,
    )
    aeronef_id = fields.Many2one(
        'manureva.aeronef',
        string="NC02",
        # string="Immatriculation de l'aéronef",
        help="Inscrire l'immatriculation de l'aéronef",
        required=True,
    )
    type_aeronef_id = fields.Many2one(
        'manureva.type_aeronef',
        string='NC03',
        # string='Type d’aéronef',
        help="Inscrire le Code OACI du modèle d'aéronef",
        required=False,
    )
    # Libellé du type d’aéronef
    lib_type_aeronef = fields.Char(
        string='NC04',
        related='type_aeronef_id.name',
        readonly=True,
    )
    vol_local_voyage = fields.Selection(
        [['L', 'Vol local'],
         ['V', 'Vol voyage'],
         ['M', 'Vol local et voyage']],
        string='NC05',
        # string='Vol local/Voyage',
        help="""
Inscrire "L" pour "vol local"
Inscrire "V" pour "vol voyage"
Inscrire "M" pour "vol local et voyage"
        """,
    )
    # Vol local
    touch_and_go = fields.Integer(
        string="NC06",
        # string="Nombre de touch and go",
        help="Inscrire le nombre de touchées avec contact avec la piste",
    )
    remise_de_gaz = fields.Integer(
        string="NC07",
        # string="Nombre de remises de gaz",
        help="Nombre de remises de gaz",
    )
    date_debut = fields.Date(
        string="NC08",
        # string="Date de début de vol",
        help="Inscrire la date réelle de début de vol",
    )
    heure_debut = fields.Char(
        string="NC09",
        # string="Heure de début de vol",
        help="Inscrire l'heure réelle de début de vol",
    )
    heure_fin = fields.Char(
        string="NC10",
        # string="Heure de fin de vol",
        help="Inscrire l'heure réelle de fin de vol",
    )
    # Vol voyage
    mouvement = fields.Selection(
        [['A', 'Arrivée'],
         ['D', 'Départ']],
        string='NC11',
        # string='Mouvement départ/arrivée',
        help="""
Inscrire "D" pour "mouvement au départ"
Inscrire "A" pour "mouvement à l'arrivée"
        """,
    )
    circonstance = fields.Selection(
        [['D', 'Dérouté'],
         ['N', 'Non dérouté'],
         ['I', 'Interrompu']],
        default='N',
        string='NC12',
        # string='Circonstance du vol',
        help="""
Inscrire "D" pour "dérouté"
Inscrire "N" pour "non dérouté"
Inscrire "I" pour interrompu
Inscrire "C" pour "circulaire"
        """,
    )
    aerod_prov_dest = fields.Many2one(
        'manureva.aerodrome',
        string='NC13',
        # string='Aérodrome de provenance/destination',
        help="Inscrire le Code OACI de l'aérodrome de provenance ou de destination",
    )
    # Libellé aérodrome de provenance/destination
    lib_aerod_prov_dest = fields.Char(
        string='NC14',
        related='aerod_prov_dest.apt_nom',
        readonly=True,
    )
    date_bloc = fields.Date(
        string='NC15',
        # string='Date bloc réelle',
        help="Inscrire la date réelle d'arrivée ou de départ du parking avion",
    )
    heure_bloc = fields.Char(
        string='NC16',
        # string='Heure bloc réelle',
        help="Inscrire l'heure locale réelle d'arrivée ou de départ du parking avion (HH:MM)",
    )
    date_piste = fields.Date(
        string='NC17',
        # string='Date piste réelle',
        help="Inscrire la date réelle d'aterrissage ou de décollage",
    )
    heure_piste = fields.Char(
        string='NC18',
        # string='Heure piste réelle',
        help="Inscrire l'heure locale réelle d'atterrissage ou de décollage (HH:MM)",
    )
    # Indicatif navigation aérienne
    ind_nav_aerienne = fields.Char(
        string='NC19',
        help='Indicatif navigation aérienne',
    )
    # Code de la piste utilisée
    pis_utilisee = fields.Char(
        string='NC20',
        help='Code de la piste utilisée',
    )
    # Régime de vol IFR/VFR
    reg_vol = fields.Selection(
        [('1', 'ol IFR'),
         ('2', 'Vol VFR avec plan de'),
         ('3', 'Vol VFR sans plan de vol'),
         ('4', 'Vol VFR sans mention de la distinction avec ou sans plan de vol')],
        string='NC21',
        help="""
        - « 1 » pour « vol IFR » ;
        - « 2 » pour « vol VFR avec plan de vol » ;
        - « 3 » pour « vol VFR sans plan de vol »;
        - « 4 » pour vol VFR sans mention de la distinction avec ou sans plan de vol
        - « S » pour « balisage en service » ;
        """,
    )
    # Balisage en service / non en service
    balisage = fields.Selection(
        [('N', 'balisage non en service'), ('S', 'balisage en service')],
        default='N',
        string='NC22',
        help="""
    Inscrire "S" pour "Balisage en service"
    Inscrire "N" pour "Balisage non en service"
            """,
    )
    # Visibilité horizontale mesurée en mètres
    vis_horizontale = fields.Integer(
        string='NC23',
        help="Visibilité horizontale mesurée en mètres",
    )
    # Nombre de passagers
    nombre_passagers = fields.Integer(
        string='NC24',
        help="Nombre de passagers",
    )
    type_voyage = fields.Selection(
        [['1', "Vol d'aéroclub"],
         ['2', 'Vol privé français'],
         ['3', 'Vol privé étranger'],
         ['4', 'Vol de travail aérien'],
         ['5', "Vol d'appareil commercial sans passager"],
         ['6', 'Autre vol']],
        string='NC25',
        # string='Type de voyage',
        help="""
Inscrire "1" pour "Vol d'aéroclub"
Inscrire "2" pour "Vol privé français"
Inscrire "3" pour "Vol privé étranger"
Inscrire "4" pour "Vol de travail aérien"
Inscrire "5" pour "Vol d'appareil commercial sans passager"
Inscrire "6" pour "autre vol"
        """,
    )

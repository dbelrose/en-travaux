# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date, datetime
import logging

_logger = logging.getLogger(__name__)


class BookingYear(models.Model):
    _name = 'booking.year'
    _description = 'Déclaration annuelle de chiffre d\'affaires'
    _order = 'year desc'
    _rec_name = 'display_name'

    # ============================================
    # IDENTIFICATION
    # ============================================

    year = fields.Integer(
        string='Année',
        required=True,
        help='Année de la déclaration'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company
    )

    display_name = fields.Char(
        string='Nom',
        compute='_compute_display_name',
        store=True
    )

    @api.depends('year', 'company_id')
    def _compute_display_name(self):
        for record in self:
            company_name = record.company_id.name if record.company_id else 'Sans société'
            record.display_name = f"Déclaration {record.year} - {company_name}"

    # ============================================
    # CHAMPS POUR LE FORMULAIRE PDF (TOUS EN TEXTE)
    # ============================================

    # Année et période
    annee = fields.Char(
        string='Année',
        compute='_compute_pdf_fields',
        store=True,
        help='Année précédente (ex: "2024")'
    )

    date_limite = fields.Char(
        string='Date limite',
        compute='_compute_pdf_fields',
        help="31/03 de l'année en cours"
    )

    date_debut = fields.Char(
        string='Date début',
        default='01/01',
        help='Constante: "01/01"'
    )

    date_fin = fields.Char(
        string='Date fin',
        default='31/12',
        help='Constante: "31/12"'
    )

    # Privilège
    privilege_oui = fields.Char(
        string='Privilège Oui',
        default='',
        help='Constante: "" (vide)'
    )

    privilege_non = fields.Char(
        string='Privilège Non',
        default='X',
        help='Constante: "X"'
    )

    # I – VENTES
    ligne_01 = fields.Char(
        string='Ligne 01',
        default='0',
        store=True,
        help='Ventes des importateurs grossistes dont la marge commerciale est inférieure ou égale à 10%'
    )
    ligne_02 = fields.Char(
        string='Ligne 02',
        default='0',
        store=True,
        help='Ventes en gros'
    )
    ligne_03 = fields.Char(
        string='Ligne 03',
        default='0',
        store=True,
        help='Ventes d’hydrocarbures au détail'
    )
    ligne_05 = fields.Char(
        string='Ligne 05',
        default='0',
        store=True,
        help='Ventes de lait frais'
    )
    ligne_06 = fields.Char(
        string='Ligne 06',
        default='0',
        store=True,
        help='Ventes de tabacs'
    )
    ligne_07 = fields.Char(
        string='Ligne 07',
        default='0',
        store=True,
        help='Ventes de farine, riz, sucre cristallisé et en poudre'
    )
    ligne_08 = fields.Char(
        string='Ligne 08',
        default='0',
        store=True,
        help='Ventes en gros de lait frais d’origine locale'
    )
    ligne_09 = fields.Char(
        string='Ligne 09',
        default='0',
        store=True,
        help='Ventes de timbres‑poste et fiscaux'
    )
    ligne_10 = fields.Char(
        string='Ligne 10',
        default='0',
        store=True,
        help='Ventes au détail supérieures à 20 millions F CFP'
    )
    ligne_11 = fields.Char(
        string='Ligne 11',
        default='0',
        store=True,
        help='Autres natures de ventes (cession de fonds de commerce, de clientèle…) à préciser :'
    )
    ligne_12 = fields.Char(
        string='Ligne 12',
        default='0',
        store=True,
        help='Ventes de coprah'
    )
    ligne_20 = fields.Char(
        string='Ligne 20',
        default='0',
        store=True,
        help='Ventes par des revendeurs de baguettes au prix de détail fixé par arrêté en conseil des ministres'
    )
    ligne_23 = fields.Char(
        string='Ligne 23',
        default='0',
        store=True,
        help='Ventes à l’aventure des armateurs de goélettes'
    )
    ligne_24 = fields.Char(
        string='Ligne 24',
        default='0',
        store=True,
        help='Ventes à l’aventure des armateurs'
    )
    ligne_26 = fields.Char(
        string='Ligne 26',
        default='0',
        store=True,
        help='Ventes à l’exportation visées à l’article LP. 184‑2 du code des impôts'
    )
    ligne_90 = fields.Char(
        string='Ligne 90',
        default='0',
        store=True,
        help='Ventes au détail inférieures ou égales à 20 millions F CFP'
    )
    ligne_94 = fields.Char(
        string='Ligne 94',
        default='0',
        store=True,
        help='Apport à une société dans les conditions visées à l’article LP.182‑2 alinéa 3 du code des impôts (voir '
             'notice)'
    )

    # II – PRESTATIONS DE SERVICE ET ASSIMILÉES
    ligne_13 = fields.Char(
        string='Ligne 13',
        default='0',
        store=True,
        help='Prestations de service des entreprises d’acconage de coprah'
    )
    ligne_14 = fields.Char(
        string='Ligne 14',
        default='0',
        store=True,
        help='Prestations de service des armateurs de goélette'
    )
    ligne_15 = fields.Char(
        string='Ligne 15',
        default='0',
        store=True,
        help='Prestations de service des entreprises de travaux publics et de constructions (hors travaux de '
             'terrassement privés)'
    )
    ligne_17 = fields.Char(
        string='Ligne 17',
        default='0',
        store=True,
        help='Autres natures de prestations de services (à préciser) :'
    )
    ligne_17_commentaire = fields.Char(
        string='Ligne 17 Commentaire',
        default='',
        help='Constante: "" (vide)'
    )
    ligne_18 = fields.Char(
        string='Ligne 18',
        default='0',
        store=True,
        help='Prestations de service : locations non meublées'
    )
    ligne_19 = fields.Char(
        string='Ligne 19',
        compute='_compute_pdf_fields',
        default='0',
        store=True,
        help='Prestations de service : locations en meublé'
    )
    ligne_22 = fields.Char(
        string='Ligne 22',
        default='0',
        store=True,
        help='Ventes des boulangeries de baguettes au prix de gros fixé par arrêté en conseil des ministres'
    )
    ligne_25 = fields.Char(
        string='Ligne 25',
        default='0',
        store=True,
        help='Prestations de service des armateurs'
    )
    ligne_27 = fields.Char(
        string='Ligne 27',
        default='0',
        store=True,
        help='Prestations de services à l’exportation visées à l’article LP. 184‑2 du code des impôts'
    )
    ligne_91 = fields.Char(
        string='Ligne 91',
        default='0',
        store=True,
        help='Prestations de service sans réduction d’impôt (concerne les professions non visées à la ligne 92)'
    )
    ligne_92 = fields.Char(
        string='Ligne 92',
        default='0',
        store=True,
        help='Prestations de service avec réduction d’impôts visées à l’article LP.188‑4 du code des impôts'
    )
    ligne_93 = fields.Char(
        string='Ligne 93',
        default='0',
        store=True,
        help='Professions libérales : avocats, notaires, huissiers, etc (voir notice d’information)'
    )
    ligne_95 = fields.Char(
        string='Ligne 95',
        default='0',
        store=True,
        help='Ventes des boulangeries de baguettes au prix de détail fixé par arrêté en conseil des ministres'
    )
    ligne_96 = fields.Char(
        string='Ligne 96',
        default='0',
        store=True,
        help='Ventes des boulangeries (hors baguettes à prix fixé par arrêté en conseil des ministres)'
    )
    ligne_97 = fields.Char(
        string='Ligne 97',
        default='0',
        store=True,
        help='Ventes de denrées alimentaires à emporter ou à consommer sur place'
    )
    ligne_98 = fields.Char(
        string='Ligne 98',
        default='0',
        store=True,
        help='Prestations de services consistant à fournir le logement (hôtellerie, pension de familles, …)'
    )
    ligne_99 = fields.Char(
        string='Ligne 99',
        default='0',
        store=True,
        help='Prestations de service : locations de terrains nus non aménagés'
    )

    ligne_a = fields.Char(
        string='Ligne A',
        default='0',
        compute='_compute_pdf_fields',
        store=True,
        help=''
    )
    ligne_b = fields.Char(
        string='Ligne B',
        default='0',
        compute='_compute_pdf_fields',
        store=True,
        help=''
    )
    ligne_a_p_c = fields.Char(
        string='Ligne A (P.C)',
        compute='_compute_pdf_fields',
        store=True,
        help='Somme des booking.import.line.rate de l\'année calendaire précédente'
    )

    ligne_b_p_d = fields.Char(
        string='Ligne B (P.D)',
        default='0',
        store=True,
        help='Constante: "0"'
    )

    ligne_c = fields.Char(
        string='Ligne C',
        compute='_compute_pdf_fields',
        store=True,
        help='Somme des booking.import.line.rate de l\'année calendaire précédente'
    )

    ligne_d = fields.Char(
        string='Ligne D',
        default='0',
        store=True,
        help='Constante: "0"'
    )

    ligne_dx = fields.Char(
        string='Ligne DX',
        default='0',
        store=True,
        help='Dont charges afférentes aux lignes 17 / 18 / 91 / 93 / 96 / 98 / 99'
    )
    ligne_dy = fields.Char(
        string='Ligne DY',
        default='0',
        store=True,
        help='Dont charges afférentes aux lignes 13 / 14 / 15 et 95'
    )

    # Date de déclaration
    date = fields.Char(
        string='Date',
        compute='_compute_pdf_fields',
        store=True,
        help='Date du jour au format JJ/MM/AAAA'
    )
    date_p_3 = fields.Char(
        string='Date',
        compute='_compute_pdf_fields',
        store=True,
        help='Date du jour au format JJ/MM/AAAA'
    )

    # Informations géographiques
    lieu = fields.Char(
        string='Lieu',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.city (address type delivery)'
    )
    lieu_p_3 = fields.Char(
        string='Lieu',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.city (address type delivery)'
    )

    adresse_geo_1 = fields.Char(
        string='Adresse géographique',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.<adresse> (address type delivery)'
    )

    adresse_geo_2 = fields.Char(
        string='Adresse géographique',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.<adresse> (address type delivery)'
    )

    adresse_geo_3 = fields.Char(
        string='Adresse géographique',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.<adresse> (address type delivery)'
    )

    adresse_pos = fields.Char(
        string='Adresse postale',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.<adresse complète>'
    )

    # Activité
    activite = fields.Char(
        string='Activité',
        compute='_compute_pdf_fields',
        store=True,
        help='booking.import.line.property_type_id.categ_id.name'
    )

    # Contact
    telephone = fields.Char(
        string='Téléphone',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.phone sinon res.users.partner_id.mobile'
    )

    email = fields.Char(
        string='Email',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.login'
    )

    # Numéro Tahiti
    numero_tahiti = fields.Char(
        string='Numéro Tahiti',
        compute='_compute_pdf_fields',
        store=True,
        help='res.company.tahiti'
    )

    numero_tahiti_2 = fields.Char(
        string='Numéro Tahiti 2',
        compute='_compute_pdf_fields',
        store=True,
        help='res.company.tahiti'
    )

    # Identité déclarant
    nom_prenom = fields.Char(
        string='Nom Prénom',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.name'
    )

    date_naissance = fields.Char(
        string='Date de naissance',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.birthdate_date au format JJ/MM/AAAA'
    )

    raison_sociale = fields.Char(
        string='Raison sociale',
        compute='_compute_pdf_fields',
        store=True,
        help='res.users.partner_id.lastname + " " + res.users.partner_id.firstname'
    )

    # ============================================
    # CHAMPS TECHNIQUES
    # ============================================

    total_revenue = fields.Monetary(
        string='CA annuel (calcul)',
        compute='_compute_total_revenue',
        currency_field='company_currency_id',
        store=True,
        help='Somme des rates pour calculs internes'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        string="Devise société",
        related='company_id.currency_id'
    )

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('declared', 'Déclaré')
    ], string='État', default='draft')

    # Contrainte d'unicité
    _sql_constraints = [
        ('unique_year_company',
         'unique(year, company_id)',
         'Une seule déclaration annuelle par année et société!')
    ]

    # ============================================
    # COMPUTED METHODS
    # ============================================

    @api.depends('year', 'company_id')
    def _compute_total_revenue(self):
        """Calcule le CA total de l'année pour toutes les propriétés de la société"""
        for record in self:
            if not record.year:
                record.total_revenue = 0.0
                continue

            # Récupérer toutes les réservations de l'année pour TOUTES les propriétés
            reservations = self.env['booking.import.line'].search([
                ('arrival_date', '>=', date(record.year, 1, 1)),
                ('arrival_date', '<=', date(record.year, 12, 31)),
                ('company_id', '=', record.company_id.id),
                ('status', '=', 'ok')
            ])

            record.total_revenue = sum(r.rate for r in reservations if r.rate)

    @api.depends('year', 'company_id', 'total_revenue')
    def _compute_pdf_fields(self):
        """Calcule tous les champs destinés au PDF"""
        for record in self:
            # Année précédente
            record.annee = str(record.year) if record.year else ""

            # Date limite
            record.date_limite = datetime(datetime.now().year, 3, 31).strftime('%d/%m/%Y')

            # Date du jour
            record.date = datetime.now().strftime('%d/%m/%Y')
            record.date_p_3 = datetime.now().strftime('%d/%m/%Y')

            # Montants financiers (formatés avec espaces comme séparateurs de milliers)
            ca_formatted = record._format_amount(record.total_revenue)
            record.ligne_19 = ca_formatted
            record.ligne_a_p_c = ca_formatted
            record.ligne_c = ca_formatted

            # Informations utilisateur
            user = self.env.user
            partner = user.partner_id

            # Nom et prénom
            record.nom_prenom = user.name or ""

            # Date de naissance
            if hasattr(partner, 'birthdate_date') and partner.birthdate_date:
                record.date_naissance = partner.birthdate_date.strftime('%d/%m/%Y')
            else:
                record.date_naissance = ""

            # Raison sociale
            if hasattr(partner, 'lastname') and hasattr(partner, 'firstname'):
                lastname = partner.lastname or ""
                firstname = partner.firstname or ""
                record.raison_sociale = f"{lastname} {firstname}".strip()
            else:
                record.raison_sociale = partner.name or ""

            # Email
            record.email = user.login or ""

            # Téléphone
            record.telephone = partner.phone or partner.mobile or ""

            # Numéro Tahiti
            tahiti_number = ""
            if hasattr(record.company_id, 'tahiti'):
                tahiti_number = str(record.company_id.tahiti or "")
            record.numero_tahiti = tahiti_number
            record.numero_tahiti_2 = tahiti_number

            # Adresses (chercher l'adresse de type delivery)
            delivery_address = partner.child_ids.filtered(
                lambda a: a.type == 'delivery'
            )[:1]

            if delivery_address:
                # Lieu (ville)
                record.lieu = record.lieu_p_3 = delivery_address.city or ""

                # Adresse géographique (street + city)
                if delivery_address.street:
                    record.adresse_geo_1 = delivery_address.street
                if delivery_address.street2:
                    record.adresse_geo_2 = delivery_address.street2
                if delivery_address.city:
                    record.adresse_geo_3 = delivery_address.city
            else:
                # Fallback sur l'adresse principale
                record.lieu = record.lieu_p_3 = partner.city or ""
                if partner.street:
                    record.adresse_geo_1 = partner.street
                if partner.street2:
                    record.adresse_geo_2 = partner.street2
                if partner.city:
                    record.adresse_geo_3 = partner.city

            # Adresse postale complète
            adresse_pos_parts = []
            if partner.street:
                adresse_pos_parts.append(partner.street)
            if partner.street2:
                adresse_pos_parts.append(partner.street2)
            if partner.zip:
                zip_city = f"{partner.zip} {partner.city}" if partner.city else partner.zip
                adresse_pos_parts.append(zip_city)
            elif partner.city:
                adresse_pos_parts.append(partner.city)
            record.adresse_pos = " - ".join(adresse_pos_parts)

            # Activité : récupérer depuis les réservations de l'année
            # On prend la catégorie de la première propriété trouvée
            reservations = record.get_year_reservations()
            if reservations and reservations[0].property_type_id and reservations[0].property_type_id.categ_id:
                record.activite = reservations[0].property_type_id.categ_id.name
            else:
                record.activite = "Location meublée"

    def _format_amount(self, amount):
        """Formate un montant avec espaces comme séparateurs de milliers"""
        if not amount:
            return "0"

        # Arrondir à l'entier
        amount_int = int(round(amount))

        # Formater avec espaces
        return f"{amount_int:,}".replace(',', ' ')

    # ============================================
    # MÉTHODES PUBLIQUES
    # ============================================

    @api.model
    def create_or_update_year(self, year, company_id=None):
        """
        Crée ou met à jour une déclaration annuelle

        Args:
            year (int): Année de la déclaration
            company_id (int, optional): ID de la société

        Returns:
            booking.year: L'enregistrement créé ou mis à jour
        """
        if company_id is None:
            company_id = self.env.company.id

        # Rechercher un enregistrement existant
        year_record = self.search([
            ('year', '=', year),
            ('company_id', '=', company_id)
        ], limit=1)

        if year_record:
            # Forcer le recalcul
            year_record._compute_total_revenue()
            year_record._compute_pdf_fields()
            return year_record
        else:
            # Créer un nouvel enregistrement
            return self.create({
                'year': year,
                'company_id': company_id,
            })

    def action_recalculate(self):
        """Force le recalcul de tous les champs"""
        self._compute_total_revenue()
        self._compute_pdf_fields()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Recalcul terminé',
                'message': f'{len(self)} déclaration(s) annuelle(s) recalculée(s)',
                'type': 'success',
            }
        }

    def action_confirm(self):
        """Confirme la déclaration"""
        self.write({'state': 'confirmed'})
        return True

    def action_declare(self):
        """Marque la déclaration comme déclarée"""
        self.write({'state': 'declared'})
        return True

    def action_export_pdf_data(self):
        """
        Prépare un dictionnaire avec toutes les données pour le PDF

        Returns:
            dict: Toutes les données au format attendu par le PDF
        """
        self.ensure_one()

        # Forcer le recalcul avant export
        self._compute_total_revenue()
        self._compute_pdf_fields()

        return {
            "annee": self.annee,
            "date_debut": self.date_debut,
            "date_fin": self.date_fin,
            "privilege_oui": self.privilege_oui,
            "privilege_non": self.privilege_non,
            "ligne_17": self.ligne_17,
            "ligne_19": self.ligne_19,
            "ligne_a_p_c": self.ligne_a_p_c,
            "ligne_b_p_d": self.ligne_b_p_d,
            "date": self.date,
            "ligne_c": self.ligne_c,
            "ligne_d": self.ligne_d,
            "ligne_dx": self.ligne_dx,
            "ligne_dy": self.ligne_dy,
            "lieu": self.lieu,
            "lieu_p_3": self.lieu_p_3,
            "adresse_geo_1": self.adresse_geo_1,
            "adresse_geo_2": self.adresse_geo_2,
            "adresse_geo_3": self.adresse_geo_3,
            "adresse_pos": self.adresse_pos,
            "activite": self.activite,
            "ligne_17_commentaire": self.ligne_17_commentaire,
            "telephone": self.telephone,
            "numero_tahiti": self.numero_tahiti,
            "numero_tahiti_2": self.numero_tahiti_2,
            "nom_prenom": self.nom_prenom,
            "date_naissance": self.date_naissance,
            "raison_sociale": self.raison_sociale,
            "email": self.email,
        }

    def get_year_reservations(self):
        """Retourne toutes les réservations de l'année pour toutes les propriétés de la société"""
        self.ensure_one()

        if self.year:
            return self.env['booking.import.line'].search([
                ('arrival_date', '>=', date(self.year, 1, 1)),
                ('arrival_date', '<=', date(self.year, 12, 31)),
                ('company_id', '=', self.company_id.id),
                ('status', '=', 'ok')
            ])

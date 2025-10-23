# -*- coding: utf-8 -*-
import base64
import logging
import re
from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_activity_image_mapping(self):
        """
        Retourne le mapping entre les activités APE et les règles d'images.
        Structure: {
            'pattern_ape': {
                'keywords': [(regex_pattern, image_path, description), ...],
                'default': (image_path, description)
            }
        }
        """
        return {
            # Sports - Code APE 9312z
            'activités de clubs de sports': {
                'keywords': [
                    # Sports de raquette
                    (r'\b(tennis(?!.*table))\b', 'os_fp_rte_sync/static/img/sports/tennis.png', 'Tennis'),
                    (r'\b(tennis[- ]de[- ]table|ping[- ]?pong)\b', 'os_fp_rte_sync/static/img/sports/table_tennis.png',
                     'Tennis de table'),
                    (r'\b(badminton)\b', 'os_fp_rte_sync/static/img/sports/badminton.png', 'Badminton'),
                    (r'\b(squash)\b', 'os_fp_rte_sync/static/img/sports/squash.png', 'Squash'),

                    # Sports de combat
                    (r'\b(judo|ju[- ]?jitsu)\b', 'os_fp_rte_sync/static/img/sports/judo.png', 'Judo'),
                    (r'\b(karate|karaté)\b', 'os_fp_rte_sync/static/img/sports/karate.png', 'Karaté'),
                    (r'\b(boxe|boxing)\b', 'os_fp_rte_sync/static/img/sports/boxing.png', 'Boxe'),
                    (r'\b(taekwondo|tae[- ]?kwon[- ]?do)\b', 'os_fp_rte_sync/static/img/sports/taekwondo.png',
                     'Taekwondo'),
                    (r'\b(lutte|wrestling)\b', 'os_fp_rte_sync/static/img/sports/wrestling.png', 'Lutte'),

                    # Sports de tir
                    (r'\b(tir à l\'arc|archerie)\b', 'os_fp_rte_sync/static/img/sports/archery.png', 'Tir à l\'arc'),
                    (r'\b(tir sportif|carabine)\b', 'os_fp_rte_sync/static/img/sports/shooting.png', 'Tir sportif'),

                    # Sports aquatiques
                    (r'\b(natation|swimming)\b', 'os_fp_rte_sync/static/img/sports/swimming.png', 'Natation'),
                    (r'\b(plongée|diving)\b', 'os_fp_rte_sync/static/img/sports/diving.png', 'Plongée'),
                    (r'\b(surf(?:ing)?)\b', 'os_fp_rte_sync/static/img/sports/surfing.png', 'Surf'),
                    (r'\b(voile|sailing)\b', 'os_fp_rte_sync/static/img/sports/sailing.png', 'Voile'),
                    (r'\b(va\'a|pirogue|outrigger)\b', 'os_fp_rte_sync/static/img/sports/vaa.png', 'Va\'a'),
                    (r'\b(kayak|canoë)\b', 'os_fp_rte_sync/static/img/sports/kayak.png', 'Kayak'),

                    # Sports collectifs
                    (
                    r'\b(football|foot(?!.*américain))\b', 'os_fp_rte_sync/static/img/sports/football.png', 'Football'),
                    (r'\b(rugby)\b', 'os_fp_rte_sync/static/img/sports/rugby.png', 'Rugby'),
                    (r'\b(basket(?:ball)?)\b', 'os_fp_rte_sync/static/img/sports/basketball.png', 'Basketball'),
                    (r'\b(volley(?:ball)?)\b', 'os_fp_rte_sync/static/img/sports/volleyball.png', 'Volleyball'),
                    (r'\b(handball|hand[- ]?ball)\b', 'os_fp_rte_sync/static/img/sports/handball.png', 'Handball'),

                    # Sports de précision
                    (r'\b(pétanque|boules)\b', 'os_fp_rte_sync/static/img/sports/petanque.png', 'Pétanque'),
                    (r'\b(golf)\b', 'os_fp_rte_sync/static/img/sports/golf.png', 'Golf'),

                    # Autres sports
                    (r'\b(athlétisme|athletics)\b', 'os_fp_rte_sync/static/img/sports/athletics.png', 'Athlétisme'),
                    (r'\b(cyclisme|vélo|cycling)\b', 'os_fp_rte_sync/static/img/sports/cycling.png', 'Cyclisme'),
                    (r'\b(équitation|horse)\b', 'os_fp_rte_sync/static/img/sports/equestrian.png', 'Équitation'),
                    (r'\b(danse|dance)\b', 'os_fp_rte_sync/static/img/sports/dance.png', 'Danse'),
                    (r'\b(fitness|musculation|gym)\b', 'os_fp_rte_sync/static/img/sports/fitness.png', 'Fitness'),
                    (r'\b(yoga)\b', 'os_fp_rte_sync/static/img/sports/yoga.png', 'Yoga'),
                ],
                'default': ('os_fp_rte_sync/static/img/sports/default_sport.png', 'Sport')
            },

            # Activités artistiques - Code APE 9003a/9003b
            'création artistique': {
                'keywords': [
                    (r'\b(peintur[e|ing]|arts? plastiques?)\b', 'os_fp_rte_sync/static/img/art/painting.png',
                     'Peinture'),
                    (r'\b(sculptur[e|ing])\b', 'os_fp_rte_sync/static/img/art/sculpture.png', 'Sculpture'),
                    (r'\b(photographie|photo)\b', 'os_fp_rte_sync/static/img/art/photography.png', 'Photographie'),
                    (r'\b(théâtre|theater)\b', 'os_fp_rte_sync/static/img/art/theater.png', 'Théâtre'),
                    (r'\b(musique|music)\b', 'os_fp_rte_sync/static/img/art/music.png', 'Musique'),
                ],
                'default': ('os_fp_rte_sync/static/img/art/default_art.png', 'Art')
            },

            # Restauration - Codes APE 5610a/5610b/5610c
            'restauration': {
                'keywords': [
                    (r'\b(pizz[ae]ria)\b', 'os_fp_rte_sync/static/img/food/pizza.png', 'Pizzeria'),
                    (r'\b(burger|hamburger)\b', 'os_fp_rte_sync/static/img/food/burger.png', 'Burger'),
                    (r'\b(sushi|japonais)\b', 'os_fp_rte_sync/static/img/food/sushi.png', 'Sushi'),
                    (r'\b(crêpe|galette)\b', 'os_fp_rte_sync/static/img/food/crepe.png', 'Crêperie'),
                    (r'\b(chinois|asiatique)\b', 'os_fp_rte_sync/static/img/food/asian.png', 'Asiatique'),
                    (r'\b(tahitien|ma\'a)\b', 'os_fp_rte_sync/static/img/food/tahitian.png', 'Tahitien'),
                    (r'\b(poisson cru|i\'a ota)\b', 'os_fp_rte_sync/static/img/food/poisson_cru.png', 'Poisson cru'),
                ],
                'default': ('os_fp_rte_sync/static/img/food/restaurant.png', 'Restaurant')
            },

            # Hébergement - Code APE 5510z
            'hôtels et hébergement': {
                'keywords': [
                    (r'\b(hôtel|hotel)\b', 'os_fp_rte_sync/static/img/accommodation/hotel.png', 'Hôtel'),
                    (r'\b(pension)\b', 'os_fp_rte_sync/static/img/accommodation/pension.png', 'Pension'),
                    (r'\b(bungalow|fare)\b', 'os_fp_rte_sync/static/img/accommodation/bungalow.png', 'Bungalow'),
                ],
                'default': ('os_fp_rte_sync/static/img/accommodation/default.png', 'Hébergement')
            },

            # Commerce - Codes APE 47xx
            'commerce de détail': {
                'keywords': [
                    (r'\b(pharmacie)\b', 'os_fp_rte_sync/static/img/commerce/pharmacy.png', 'Pharmacie'),
                    (r'\b(boulangerie|pain)\b', 'os_fp_rte_sync/static/img/commerce/bakery.png', 'Boulangerie'),
                    (r'\b(fleuriste|fleurs)\b', 'os_fp_rte_sync/static/img/commerce/florist.png', 'Fleuriste'),
                    (r'\b(librairie|livres)\b', 'os_fp_rte_sync/static/img/commerce/bookstore.png', 'Librairie'),
                ],
                'default': ('os_fp_rte_sync/static/img/commerce/shop.png', 'Commerce')
            },
        }

    @api.model
    def _get_default_image_by_category(self, name, category_ids):
        """
        Analyse le nom et les catégories pour déterminer l'image appropriée.

        :param name: Nom du partenaire
        :param category_ids: Recordset des catégories du partenaire
        :return: Tuple (image_data_base64, description) ou (None, None)
        """
        if not name or not category_ids:
            return None, None

        # Normaliser le nom pour la recherche
        name_lower = name.lower()

        # Récupérer les catégories APE (enfants de la catégorie parente "APE")
        ape_parent = self.env['res.partner.category'].search([
            ('name', '=', 'APE'),
            ('parent_id', '=', False)
        ], limit=1)

        if not ape_parent:
            return None, None

        # Filtrer les catégories APE du partenaire
        ape_categories = category_ids.filtered(lambda c: c.parent_id == ape_parent)

        if not ape_categories:
            return None, None

        # Récupérer le mapping
        mapping = self._get_activity_image_mapping()

        # Parcourir les catégories APE
        for ape_cat in ape_categories:
            ape_name_lower = ape_cat.name.lower()

            # Chercher une correspondance dans le mapping
            for pattern_key, config in mapping.items():
                if pattern_key in ape_name_lower:
                    # Chercher des mots-clés dans le nom
                    for keyword_regex, image_path, description in config['keywords']:
                        if re.search(keyword_regex, name_lower, re.IGNORECASE):
                            _logger.info(
                                "Image auto: '%s' matched pattern '%s' for category '%s' => %s",
                                name, keyword_regex, ape_cat.name, description
                            )
                            image_data = self._load_image_from_path(image_path)
                            if image_data:
                                return image_data, description

                    # Si aucun mot-clé ne correspond, utiliser l'image par défaut de la catégorie
                    if 'default' in config:
                        default_path, default_desc = config['default']
                        _logger.info(
                            "Image auto: '%s' using default for category '%s' => %s",
                            name, ape_cat.name, default_desc
                        )
                        image_data = self._load_image_from_path(default_path)
                        if image_data:
                            return image_data, default_desc

        return None, None

    @api.model
    def _load_image_from_path(self, image_path):
        """
        Charge une image depuis un chemin de module et la retourne en base64.

        :param image_path: Chemin relatif au module (ex: 'module/static/img/sport.png')
        :return: Image encodée en base64 ou None
        """
        try:
            image_data = tools.image_process(
                tools.file_open(image_path, 'rb').read(),
                size=(1920, 1920),
                verify_resolution=False
            )
            return base64.b64encode(image_data)
        except Exception as e:
            _logger.warning("Cannot load image from %s: %s", image_path, str(e))
            return None

    @api.model
    def _auto_assign_image(self, partner):
        """
        Assigne automatiquement une image au partenaire si nécessaire.

        :param partner: Recordset res.partner
        :return: Boolean - True si une image a été assignée
        """
        # Ne rien faire si le partenaire a déjà une image
        if partner.image_1920:
            return False

        # Ne traiter que les entreprises
        if not partner.is_company:
            return False

        # Récupérer l'image appropriée
        image_data, description = self._get_default_image_by_category(
            partner.name,
            partner.category_id
        )

        if image_data:
            partner.write({'image_1920': image_data})
            _logger.info(
                "Auto-assigned image to partner '%s' (ID: %s): %s",
                partner.name, partner.id, description
            )
            return True

        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour assigner automatiquement les images."""
        partners = super(ResPartner, self).create(vals_list)

        # Assigner les images après création (pour avoir les catégories)
        for partner in partners:
            if partner.is_company and not partner.image_1920:
                self._auto_assign_image(partner)

        return partners

    def write(self, vals):
        """Override write pour assigner automatiquement les images."""
        res = super(ResPartner, self).write(vals)

        # Si le nom ou les catégories changent, réassigner l'image
        if ('name' in vals or 'category_id' in vals) and not vals.get('image_1920'):
            for partner in self:
                if partner.is_company and not partner.image_1920:
                    self._auto_assign_image(partner)

        return res

    @api.model
    def action_batch_assign_images(self):
        """
        Action pour assigner en masse les images aux partenaires existants.
        À utiliser via un bouton ou un cron.
        """
        partners = self.search([
            ('is_company', '=', True),
            ('image_1920', '=', False),
            ('category_id', '!=', False)
        ])

        count = 0
        for partner in partners:
            if self._auto_assign_image(partner):
                count += 1

        _logger.info("Batch image assignment: %s images assigned on %s partners", count, len(partners))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attribution des images',
                'message': f"{count} images assignées sur {len(partners)} partenaires.",
                'type': 'success',
                'sticky': False,
            },
        }

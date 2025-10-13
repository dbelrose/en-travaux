# -*- coding: utf-8 -*-
"""
Système avancé d'attribution d'images pour res.partner

Améliorations :
1. Stockage des images via ir.attachment (filestore)
2. Génération à la volée lors de l'import
3. Utilisation de Font Awesome pour générer les images
"""

import base64
import hashlib
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from odoo import api, fields, models, tools

_logger = logging.getLogger(__name__)


class ResPartnerImageGenerator(models.AbstractModel):
    """Générateur d'images pour les partenaires basé sur Font Awesome"""
    _name = 'res.partner.image.generator'
    _description = 'Générateur d\'images pour partenaires'

    @api.model
    def _get_fontawesome_mapping(self):
        """
        Retourne le mapping entre activités et icônes Font Awesome.

        Font Awesome icons: https://fontawesome.com/icons
        Format: Unicode character codes

        Note: Odoo inclut Font Awesome 5 Free (solid style)
        """
        return {
            # Sports
            'activités de clubs de sports': {
                'keywords': [
                    # Sports de raquette
                    (r'\b(tennis(?!.*table))\b', '\uf45d', '#2ecc71', 'Tennis'),  # fa-table-tennis
                    (r'\b(tennis[- ]de[- ]table|ping[- ]?pong)\b', '\uf45d', '#3498db', 'Tennis de table'),
                    (r'\b(badminton)\b', '\uf45d', '#9b59b6', 'Badminton'),

                    # Sports de combat
                    (r'\b(judo|ju[- ]?jitsu|karate|karaté)\b', '\uf6cf', '#e67e22', 'Arts martiaux'),  # fa-fist-raised
                    (r'\b(boxe|boxing)\b', '\uf6cf', '#e74c3c', 'Boxe'),

                    # Sports aquatiques
                    (r'\b(natation|swimming)\b', '\uf5c4', '#3498db', 'Natation'),  # fa-swimmer
                    (r'\b(plongée|diving)\b', '\uf5c4', '#1abc9c', 'Plongée'),
                    (r'\b(surf(?:ing)?|bodyboard)\b', '\uf3ed', '#16a085', 'Surf'),  # fa-water
                    (r'\b(voile|sailing)\b', '\ue532', '#2980b9', 'Voile'),  # fa-sailboat
                    (r'\b(va\'?a|pirogue|kayak)\b', '\uf21a', '#27ae60', 'Pirogue'),  # fa-ship

                    # Sports collectifs
                    (r'\b(football|foot(?!.*américain)|soccer)\b', '\uf1e3', '#2ecc71', 'Football'),  # fa-futbol
                    (r'\b(rugby)\b', '\uf1e3', '#8e44ad', 'Rugby'),
                    (r'\b(basket(?:ball)?)\b', '\uf434', '#e67e22', 'Basketball'),  # fa-basketball-ball
                    (r'\b(volley(?:ball)?)\b', '\uf45f', '#f39c12', 'Volleyball'),  # fa-volleyball-ball

                    # Autres sports
                    (r'\b(cyclisme|vélo|cycling)\b', '\uf206', '#c0392b', 'Cyclisme'),  # fa-bicycle
                    (r'\b(golf)\b', '\uf450', '#27ae60', 'Golf'),  # fa-golf-ball
                    (r'\b(danse|dance)\b', '\uf8e8', '#e91e63', 'Danse'),  # fa-person-dress
                    (r'\b(fitness|musculation|gym)\b', '\uf44b', '#34495e', 'Fitness'),  # fa-dumbbell
                    (r'\b(yoga)\b', '\uf1e4', '#9c27b0', 'Yoga'),  # fa-spa
                ],
                'default': ('\uf1e3', '#95a5a6', 'Sport')  # fa-futbol
            },

            # Arts et culture
            'création artistique': {
                'keywords': [
                    (r'\b(peintur[e|ing]|arts? plastiques?)\b', '\uf53f', '#9b59b6', 'Peinture'),  # fa-palette
                    (r'\b(photographie|photo)\b', '\uf030', '#34495e', 'Photographie'),  # fa-camera
                    (r'\b(théâtre|theater)\b', '\uf630', '#e74c3c', 'Théâtre'),  # fa-theater-masks
                    (r'\b(musique|music)\b', '\uf001', '#3498db', 'Musique'),  # fa-music
                    (r'\b(cinéma|film)\b', '\uf008', '#2c3e50', 'Cinéma'),  # fa-film
                ],
                'default': ('\uf53f', '#9b59b6', 'Art')  # fa-palette
            },

            # Restauration
            'restauration': {
                'keywords': [
                    (r'\b(pizz[ae]ria)\b', '\uf817', '#e67e22', 'Pizzeria'),  # fa-pizza-slice
                    (r'\b(burger|hamburger)\b', '\uf805', '#d35400', 'Burger'),  # fa-hamburger
                    (r'\b(sushi|japonais)\b', '\uf6e2', '#1abc9c', 'Sushi'),  # fa-fish
                    (r'\b(tahitien|ma\'?a)\b', '\uf2e7', '#16a085', 'Tahitien'),  # fa-utensils
                    (r'\b(snack|roulotte)\b', '\uf818', '#f39c12', 'Snack'),  # fa-hotdog
                ],
                'default': ('\uf2e7', '#e67e22', 'Restaurant')  # fa-utensils
            },

            # Hébergement
            'hôtels et hébergement': {
                'keywords': [
                    (r'\b(hôtel|hotel)\b', '\uf594', '#3498db', 'Hôtel'),  # fa-hotel
                    (r'\b(pension|bungalow|fare)\b', '\uf015', '#27ae60', 'Pension'),  # fa-home
                ],
                'default': ('\uf594', '#3498db', 'Hébergement')  # fa-hotel
            },

            # Commerce
            'commerce de détail': {
                'keywords': [
                    (r'\b(pharmacie)\b', '\uf484', '#e74c3c', 'Pharmacie'),  # fa-prescription-bottle
                    (r'\b(boulangerie|pain)\b', '\uf805', '#d35400', 'Boulangerie'),  # fa-bread-slice
                    (r'\b(fleuriste|fleurs)\b', '\uf7ae', '#e91e63', 'Fleuriste'),  # fa-seedling
                    (r'\b(librairie|livres)\b', '\uf02d', '#34495e', 'Librairie'),  # fa-book
                    (r'\b(supermarché)\b', '\uf07a', '#27ae60', 'Supermarché'),  # fa-shopping-cart
                    (r'\b(bijouterie|perles)\b', '\uf3ff', '#9c27b0', 'Bijouterie'),  # fa-gem
                ],
                'default': ('\uf290', '#95a5a6', 'Commerce')  # fa-shopping-bag
            },
        }

    @api.model
    def _generate_image_from_icon(self, unicode_char, color_hex, size=(1920, 1920)):
        """
        Génère une image PNG à partir d'une icône Font Awesome.

        Args:
            unicode_char: Caractère unicode de l'icône (ex: '\uf1e3')
            color_hex: Couleur en hexadécimal (ex: '#3498db')
            size: Tuple (width, height) de l'image finale

        Returns:
            bytes: Image PNG encodée en base64
        """
        try:
            # Créer une image avec fond transparent
            img = Image.new('RGBA', size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)

            # Convertir la couleur hex en RGB
            color_hex = color_hex.lstrip('#')
            rgb = tuple(int(color_hex[i:i + 2], 16) for i in (0, 2, 4))

            # Ajouter un cercle de fond avec la couleur
            margin = size[0] // 10
            circle_bbox = [margin, margin, size[0] - margin, size[1] - margin]
            draw.ellipse(circle_bbox, fill=rgb + (255,))

            # Charger la police Font Awesome
            # Odoo inclut Font Awesome, on utilise le chemin standard
            font_paths = [
                '/usr/share/fonts/truetype/font-awesome/fontawesome-webfont.ttf',
                tools.config.filestore('addons/web/static/lib/fontawesome/fonts/fontawesome-webfont.ttf'),
                'addons/web/static/lib/fontawesome/fonts/fontawesome-webfont.ttf',
            ]

            font = None
            icon_size = int(size[0] * 0.5)  # L'icône fait 50% de la taille

            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, icon_size)
                    break
                except Exception:
                    continue

            if not font:
                _logger.warning("Font Awesome not found, using default font")
                font = ImageFont.load_default()

            # Dessiner l'icône centrée
            # Note: Font Awesome utilise des caractères Unicode
            bbox = draw.textbbox((0, 0), unicode_char, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            x = (size[0] - text_width) // 2
            y = (size[1] - text_height) // 2

            # Dessiner l'icône en blanc
            draw.text((x, y), unicode_char, fill=(255, 255, 255, 255), font=font)

            # Convertir en PNG
            output = io.BytesIO()
            img.save(output, format='PNG')
            img_data = output.getvalue()

            # Redimensionner et optimiser
            img_data = tools.image_process(img_data, size=size, verify_resolution=False)

            return base64.b64encode(img_data)

        except Exception as e:
            _logger.error(f"Error generating image from icon: {e}")
            return None

    @api.model
    def _get_image_cache_key(self, unicode_char, color_hex):
        """Génère une clé de cache unique pour une icône/couleur."""
        return hashlib.md5(f"{unicode_char}_{color_hex}".encode()).hexdigest()

    @api.model
    def _get_cached_image(self, unicode_char, color_hex):
        """
        Récupère une image depuis le cache (ir.attachment).

        Returns:
            base64 encoded image or None
        """
        cache_key = self._get_image_cache_key(unicode_char, color_hex)

        attachment = self.env['ir.attachment'].sudo().search([
            ('name', '=', f'partner_icon_{cache_key}.png'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),  # Image générique, pas liée à un partenaire spécifique
        ], limit=1)

        if attachment:
            _logger.debug(f"Image found in cache: {cache_key}")
            return attachment.datas

        return None

    @api.model
    def _cache_image(self, unicode_char, color_hex, image_data):
        """
        Stocke une image générée dans le cache (ir.attachment).
        """
        cache_key = self._get_image_cache_key(unicode_char, color_hex)

        # Vérifier si déjà en cache
        existing = self.env['ir.attachment'].sudo().search([
            ('name', '=', f'partner_icon_{cache_key}.png'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ], limit=1)

        if existing:
            return existing

        # Créer l'attachment
        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'partner_icon_{cache_key}.png',
            'type': 'binary',
            'datas': image_data,
            'res_model': 'res.partner',
            'res_id': 0,  # Image générique
            'mimetype': 'image/png',
            'public': False,
            'description': f'Generated partner icon: {unicode_char} {color_hex}',
        })

        _logger.info(f"Image cached: {cache_key} (attachment #{attachment.id})")
        return attachment

    @api.model
    def get_or_generate_image(self, unicode_char, color_hex):
        """
        Récupère ou génère une image d'icône.

        1. Cherche dans le cache (ir.attachment)
        2. Si pas trouvé, génère l'image
        3. Stocke dans le cache
        4. Retourne l'image

        Returns:
            base64 encoded image
        """
        # Essayer de récupérer depuis le cache
        cached_image = self._get_cached_image(unicode_char, color_hex)
        if cached_image:
            return cached_image

        # Générer l'image
        _logger.info(f"Generating new image for icon {unicode_char} color {color_hex}")
        image_data = self._generate_image_from_icon(unicode_char, color_hex)

        if not image_data:
            return None

        # Mettre en cache
        self._cache_image(unicode_char, color_hex, image_data)

        return image_data


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_icon_for_activity(self, name, category_ids):
        """
        Analyse le nom et les catégories pour déterminer l'icône appropriée.

        Returns:
            Tuple (unicode_char, color_hex, description) or (None, None, None)
        """
        if not name or not category_ids:
            return None, None, None

        # Normaliser le nom
        name_lower = name.lower()

        # Récupérer les catégories APE
        ape_parent = self.env['res.partner.category'].search([
            ('name', '=', 'APE'),
            ('parent_id', '=', False)
        ], limit=1)

        if not ape_parent:
            return None, None, None

        ape_categories = category_ids.filtered(lambda c: c.parent_id == ape_parent)

        if not ape_categories:
            return None, None, None

        # Récupérer le mapping Font Awesome
        generator = self.env['res.partner.image.generator']
        mapping = generator._get_fontawesome_mapping()

        # Parcourir les catégories APE
        for ape_cat in ape_categories:
            ape_name_lower = ape_cat.name.lower()

            # Chercher une correspondance
            for pattern_key, config in mapping.items():
                if pattern_key in ape_name_lower:
                    # Chercher des mots-clés dans le nom
                    import re
                    for keyword_regex, unicode_char, color_hex, description in config['keywords']:
                        if re.search(keyword_regex, name_lower, re.IGNORECASE):
                            _logger.info(
                                f"Icon match: '{name}' => {description} ({unicode_char}, {color_hex})"
                            )
                            return unicode_char, color_hex, description

                    # Si aucun mot-clé, utiliser le défaut
                    if 'default' in config:
                        unicode_char, color_hex, description = config['default']
                        _logger.info(
                            f"Icon default: '{name}' => {description} ({unicode_char}, {color_hex})"
                        )
                        return unicode_char, color_hex, description

        return None, None, None

    @api.model
    def _auto_assign_image(self, partner):
        """
        Assigne automatiquement une image générée au partenaire.
        Utilise le système de cache via ir.attachment.

        Returns:
            Boolean - True si une image a été assignée
        """
        # Ne rien faire si le partenaire a déjà une image
        if partner.image_1920:
            return False

        # Ne traiter que les entreprises
        if not partner.is_company:
            return False

        # Récupérer l'icône appropriée
        unicode_char, color_hex, description = self._get_icon_for_activity(
            partner.name,
            partner.category_id
        )

        if not unicode_char:
            return False

        # Générer ou récupérer l'image depuis le cache
        generator = self.env['res.partner.image.generator']
        image_data = generator.get_or_generate_image(unicode_char, color_hex)

        if image_data:
            partner.write({'image_1920': image_data})
            _logger.info(
                f"Auto-assigned generated image to partner '{partner.name}' (ID: {partner.id}): {description}"
            )
            return True

        return False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create pour assigner automatiquement les images."""
        partners = super(ResPartner, self).create(vals_list)

        # Vérifier si l'auto-attribution est activée
        auto_assign = self.env['ir.config_parameter'].sudo().get_param(
            'fp_rte_sync.auto_assign_images',
            default='True'
        ).lower() in ('1', 'true', 'yes', 'y')

        if not auto_assign:
            return partners

        # Assigner les images après création (pour avoir les catégories)
        for partner in partners:
            if partner.is_company and not partner.image_1920:
                self._auto_assign_image(partner)

        return partners

    def write(self, vals):
        """Override write pour assigner automatiquement les images."""
        res = super(ResPartner, self).write(vals)

        # Vérifier si l'auto-attribution est activée
        auto_assign = self.env['ir.config_parameter'].sudo().get_param(
            'fp_rte_sync.auto_assign_images',
            default='True'
        ).lower() in ('1', 'true', 'yes', 'y')

        if not auto_assign:
            return res

        # Si le nom ou les catégories changent, réassigner l'image
        if ('name' in vals or 'category_id' in vals) and not vals.get('image_1920'):
            for partner in self:
                if partner.is_company and not partner.image_1920:
                    self._auto_assign_image(partner)

        return res

    @api.model
    def action_clear_image_cache(self):
        """
        Action pour vider le cache des images générées.
        Utile lors de modifications du système de génération.
        """
        attachments = self.env['ir.attachment'].sudo().search([
            ('name', 'like', 'partner_icon_%'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ])

        count = len(attachments)
        attachments.unlink()

        _logger.info(f"Cleared {count} cached partner icons from ir.attachment")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache vidé',
                'message': f"{count} images en cache supprimées.",
                'type': 'success',
                'sticky': False,
            },
        }

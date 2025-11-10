# Fichier: os_fp_rte_sync/models/res_partner_image_generator.py
# Imports à mettre à jour en haut du fichier

import base64
import hashlib
import io
import logging
import os
import re

from PIL import Image, ImageDraw, ImageFont
from odoo import api, models, tools
from odoo.modules import get_module_path

_logger = logging.getLogger(__name__)

fa_version = '7'


class ResPartnerImageGenerator(models.AbstractModel):
    """Générateur d'images pour les partenaires basé sur Font Awesome"""
    _name = 'res.partner.image.generator'
    _description = "Générateur d'images pour partenaires"

    def _load_fa_font(self, icon_size: int):
        # Récupérer le chemin du module
        module_name = self._module
        module_path = get_module_path(module_name)

        """
        Charge Font Awesome 6 avec support conteneur Docker.
        Cherche dans plusieurs emplacements possibles.
        """
        _logger.info("=" * 80)
        _logger.info("DIAGNOSTIC CHARGEMENT FONT AWESOME (Odoo 17 + Docker)")
        _logger.info("=" * 80)
        _logger.info(f"module_path : {module_path}")

        # 1) Chemins possibles (ordre de priorité)
        candidates = [
            # Chemin Docker/conteneur (PRIORITÉ 1)
            f'/mnt/extra-addons/os_fp_rte_sync/static/fonts/Font Awesome {fa_version} Free-Solid-900.otf',
            f'{module_path}/static/fonts/Font Awesome {fa_version} Free-Solid-900.otf',

            # Chemin via tools.misc.file_path (fallback)
            tools.misc.file_path(f'os_fp_rte_sync/static/fonts/Font Awesome {fa_version} Free-Solid-900.otf'),

            # Chemins système
            '/usr/share/fonts/opentype/font-awesome/FontAwesome.otf',
            '/usr/share/fonts/truetype/font-awesome/fontawesome-webfont.ttf',
            '/usr/share/fonts-font-awesome/fonts/FontAwesome.otf',
        ]

        _logger.info("Recherche des fonts embarquées...")
        for i, path in enumerate(candidates, 1):
            if not path:
                continue
            _logger.info("  [%d] %s", i, path)
            if os.path.exists(path):
                _logger.info(f"  ✓ TROUVÉ dans {path}")
                try:
                    font = ImageFont.truetype(path, icon_size)
                    _logger.info("✓ Font chargée avec succès")
                    _logger.info("  Path: %s", path)
                    _logger.info("  Size: %d", icon_size)
                    _logger.info("=" * 80)
                    return font
                except Exception as e:
                    _logger.error("✗ ERREUR lors du chargement : %s", e)
                    continue

        # 2) FALLBACK lisible (DejaVuSans - pas de FA)
        _logger.warning("⚠ Font Awesome NON TROUVÉE - utilisation de DejaVuSans")
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(icon_size * 0.8))
            _logger.info("✓ Font système fallback chargée : DejaVuSans")
            _logger.info("=" * 80)
            return font
        except Exception as e:
            _logger.error("✗ DejaVuSans not found : %s", e)
            _logger.warning("⚠ DERNIER FALLBACK : PIL default (très petit)")
            _logger.info("=" * 80)
            return ImageFont.load_default()

    @api.model
    def _get_fontawesome_mapping(self):
        """
        Mapping entre activités et icônes Font Awesome (FA6 Free - solid).
        """
        return {
            # Sports
            ' sport': {
                'keywords': [
                    (r'\b(tennis(?!.*table))\b', '\uf45d', '#2ecc71', 'Tennis'),
                    (r'\b(tennis[- ]de[- ]table|ping[- ]?pong)\b', '\uf45d', '#3498db', 'Tennis de table'),
                    (r'\b(badminton)\b', '\uf45d', '#9b59b6', 'Badminton'),
                    (r'\b(judo|ju[- ]?jitsu|karate|karaté)\b', '\uf6cf', '#e67e22', 'Arts martiaux'),
                    (r'\b(boxe|boxing)\b', '\uf6cf', '#e74c3c', 'Boxe'),
                    (r'\b(natation|swimming)\b', '\uf5c4', '#3498db', 'Natation'),
                    (r'\b(plongée|diving)\b', '\uf5c4', '#1abc9c', 'Plongée'),
                    (r'\b(surf(?:ing)?|bodyboard)\b', '\uf3ed', '#16a085', 'Surf'),
                    (r'\b(voile|sailing)\b', '\ue532', '#2980b9', 'Voile'),
                    (r"\b(va'a|pirogue|kayak)\b", '\uf21a', '#27ae60', 'Pirogue'),
                    (r'\b(football|foot(?!.*américain)|soccer)\b', '\uf1e3', '#2ecc71', 'Football'),
                    (r'\b(rugby)\b', '\uf1e3', '#8e44ad', 'Rugby'),
                    (r'\b(basket(?:ball)?)\b', '\uf434', '#e67e22', 'Basketball'),
                    (r'\b(volley(?:ball)?)\b', '\uf45f', '#f39c12', 'Volleyball'),
                    (r'\b(cyclisme|vélo|cycling)\b', '\uf206', '#c0392b', 'Cyclisme'),
                    (r'\b(golf)\b', '\uf450', '#27ae60', 'Golf'),
                    (r'\b(danse|dance)\b', '\uf8e8', '#e91e63', 'Danse'),
                    (r'\b(fitness|musculation|gym)\b', '\uf44b', '#34495e', 'Fitness'),
                    (r'\b(yoga)\b', '\uf1e4', '#9c27b0', 'Yoga'),
                ],
                'default': ('\uf1e3', '#95a5a6', 'Sport'),
            },

            # Arts et culture
            ' artistique': {
                'keywords': [
                    (r'\b(peintur[e|ing]|arts? plastiques?)\b', '\uf53f', '#9b59b6', 'Peinture'),
                    (r'\b(photographie|photo)\b', '\uf030', '#34495e', 'Photographie'),
                    (r'\b(théâtre|theater)\b', '\uf630', '#e74c3c', 'Théâtre'),
                    (r'\b(musique|music)\b', '\uf001', '#3498db', 'Musique'),
                    (r'\b(cinéma|film)\b', '\uf008', '#2c3e50', 'Cinéma'),
                ],
                'default': ('\uf53f', '#9b59b6', 'Art'),
            },

            # Restauration
            'restauration': {
                'keywords': [
                    (r'\b(pizz[ae]ria)\b', '\uf817', '#e67e22', 'Pizzeria'),
                    (r'\b(burger|hamburger)\b', '\uf805', '#d35400', 'Burger'),
                    (r'\b(sushi|japonais)\b', '\uf6e2', '#1abc9c', 'Sushi'),
                    (r"\b(tahitien|ma'a)\b", '\uf2e7', '#16a085', 'Tahitien'),
                    (r'\b(snack|roulotte)\b', '\uf818', '#f39c12', 'Snack'),
                ],
                'default': ('\uf2e7', '#e67e22', 'Restaurant'),
            },

            # Hébergement
            'hébergement': {
                'keywords': [
                    (r'\b(hôtel|hotel)\b', '\uf594', '#3498db', 'Hôtel'),
                    (r'\b(pension|bungalow|fare)\b', '\uf015', '#27ae60', 'Pension'),
                ],
                'default': ('\uf594', '#3498db', 'Hébergement'),
            },

            # Commerce de détail
            'commerce': {
                'keywords': [
                    (r'\b(pharmacie)\b', '\uf484', '#e74c3c', 'Pharmacie'),
                    (r'\b(boulangerie|pain)\b', '\uf305', '#d35400', 'Boulangerie'),
                    (r'\b(fleuriste|fleurs)\b', '\uf7ae', '#e91e63', 'Fleuriste'),
                    (r'\b(libr?airie|livres)\b', '\uf02d', '#34495e', 'Librairie'),
                    (r'\b(supermarché)\b', '\uf07a', '#27ae60', 'Supermarché'),
                    (r'\b(bijouterie|perles)\b', '\uf3ff', '#9c27b0', 'Bijouterie'),
                ],
                'default': ('\uf290', '#95a5a6', 'Commerce'),
            },
        }

    @api.model
    def _generate_image_from_icon(self, unicode_char, color_hex, size=(1920, 1920)):
        """Génère une image PNG à partir d'une icône Font Awesome."""
        try:
            _logger.info("Génération image : char=%s color=%s", repr(unicode_char), color_hex)

            img = Image.new('RGBA', size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(img)

            _hex = color_hex.lstrip('#')
            rgb = tuple(int(_hex[i:i + 2], 16) for i in (0, 2, 4))

            margin = size[0] // 10
            circle_bbox = [margin, margin, size[0] - margin, size[1] - margin]
            draw.ellipse(circle_bbox, fill=rgb + (255,))

            icon_size = int(size[0] * 0.55)
            font = self._load_fa_font(icon_size)

            _logger.info("Font chargée : %s (size=%d)", font, icon_size)

            bbox = draw.textbbox((0, 0), unicode_char, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (size[0] - text_width) // 2
            y = (size[1] - text_height) // 2

            _logger.info("Position icône : x=%d y=%d (bbox=%s)", x, y, bbox)

            draw.text((x, y), unicode_char, fill=(255, 255, 255, 255), font=font)

            output = io.BytesIO()
            img.save(output, format='PNG')
            img_data = output.getvalue()

            img_data = tools.image_process(img_data, size=size, verify_resolution=False)
            result = base64.b64encode(img_data)

            _logger.info("✓ Image générée avec succès (size=%d bytes)", len(result))
            return result

        except Exception as e:
            _logger.error("✗ Erreur lors de la génération d'image : %s", e, exc_info=True)
            return None

    @api.model
    def _get_image_cache_key(self, unicode_char, color_hex):
        """Génère une clé de cache unique pour une icône/couleur."""
        return hashlib.md5(f"{unicode_char}_{color_hex}".encode()).hexdigest()

    @api.model
    def _get_cached_image(self, unicode_char, color_hex):
        """Récupère une image depuis le cache (ir.attachment)."""
        cache_key = self._get_image_cache_key(unicode_char, color_hex)
        attachment = self.env['ir.attachment'].sudo().search([
            ('name', '=', f'partner_icon_{cache_key}.png'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ], limit=1)
        if attachment:
            _logger.debug("Image trouvée en cache : %s", cache_key)
            return attachment.datas
        return None

    @api.model
    def _cache_image(self, unicode_char, color_hex, image_data):
        """Stocke une image générée dans le cache (ir.attachment)."""
        cache_key = self._get_image_cache_key(unicode_char, color_hex)

        existing = self.env['ir.attachment'].sudo().search([
            ('name', '=', f'partner_icon_{cache_key}.png'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ], limit=1)
        if existing:
            return existing

        attachment = self.env['ir.attachment'].sudo().create({
            'name': f'partner_icon_{cache_key}.png',
            'type': 'binary',
            'datas': image_data,
            'res_model': 'res.partner',
            'res_id': 0,
            'mimetype': 'image/png',
            'public': False,
            'description': f'Generated partner icon: {unicode_char} {color_hex}',
        })
        _logger.info("Image mise en cache : %s (attachment #%s)", cache_key, attachment.id)
        return attachment

    @api.model
    def get_or_generate_image(self, unicode_char, color_hex):
        """Récupère ou génère une image d'icône."""
        cached_image = self._get_cached_image(unicode_char, color_hex)
        if cached_image:
            return cached_image

        _logger.info("Génération nouvelle image : %s %s", repr(unicode_char), color_hex)
        image_data = self._generate_image_from_icon(unicode_char, color_hex)
        if not image_data:
            return None

        self._cache_image(unicode_char, color_hex, image_data)
        return image_data


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _get_icon_for_activity(self, name, category_ids):
        """Analyse le nom et les catégories pour déterminer l'icône appropriée."""
        if not name or not category_ids:
            return None, None, None

        name_lower = name.lower()

        ape_parent = self.env['res.partner.category'].search([
            ('name', '=', 'APE'),
            ('parent_id', '=', False)
        ], limit=1)
        if not ape_parent:
            return None, None, None

        ape_categories = category_ids.filtered(lambda c: c.parent_id == ape_parent)
        if not ape_categories:
            return None, None, None

        generator = self.env['res.partner.image.generator']
        mapping = generator._get_fontawesome_mapping()

        for ape_cat in ape_categories:
            ape_name_lower = ape_cat.name.lower()

            for pattern_key, config in mapping.items():
                if pattern_key in ape_name_lower:
                    for keyword_regex, unicode_char, color_hex, description in config['keywords']:
                        if re.search(keyword_regex, name_lower, re.IGNORECASE):
                            _logger.info("✓ Icône trouvée : '%s' => %s (%s, %s)", name, description, repr(unicode_char),
                                         color_hex)
                            return unicode_char, color_hex, description

                    if 'default' in config:
                        unicode_char, color_hex, description = config['default']
                        _logger.info("✓ Icône par défaut : '%s' => %s (%s, %s)", name, description, repr(unicode_char),
                                     color_hex)
                        return unicode_char, color_hex, description

        return None, None, None

    @api.model
    def _auto_assign_image(self, partner):
        """Assigne automatiquement une image générée au partenaire."""
        if partner.image_1920:
            return False

        if not partner.is_company:
            return False

        unicode_char, color_hex, description = self._get_icon_for_activity(
            partner.name,
            partner.category_id
        )
        if not unicode_char:
            return False

        generator = self.env['res.partner.image.generator']
        image_data = generator.get_or_generate_image(unicode_char, color_hex)
        if image_data:
            partner.write({'image_1920': image_data})
            _logger.info("✓ Image auto-assignée '%s' au partenaire '%s' (ID: %s): %s",
                         color_hex, partner.name, partner.id, description)
            return True

        return False

    @api.model
    def action_clear_image_cache(self):
        """Action pour vider le cache des images."""
        attachments = self.env['ir.attachment'].sudo().search([
            ('name', 'like', 'partner_icon_%'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ])
        count = len(attachments)
        attachments.unlink()
        _logger.info("Cache vidé : %s images supprimées", count)
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

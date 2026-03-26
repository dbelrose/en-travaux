import base64
import logging
from odoo import api, models, fields

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # Cache des images générées (au niveau de la classe, partagé entre instances)
    _image_cache = {}

    @api.model
    def _get_cached_or_generate_image(self, image_key, naf_code=None):
        """
        Récupère une image depuis le cache ou la génère.

        :param image_key: Clé unique pour identifier l'image (ex: "sport", "commerce", etc.)
        :param naf_code: Code NAF optionnel pour affiner la génération
        :return: Image encodée en base64 ou False
        """
        # Vérifier le cache en mémoire
        if image_key in self._image_cache:
            _logger.debug(f"Image '{image_key}' récupérée depuis le cache mémoire")
            return self._image_cache[image_key]

        # Vérifier le cache en base de données (ir.attachment)
        cache_name = f"partner_image_cache_{image_key}"
        attachment = self.env['ir.attachment'].sudo().search([
            ('name', '=', cache_name),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),  # Pas attaché à un partenaire spécifique
        ], limit=1)

        if attachment and attachment.datas:
            _logger.debug(f"Image '{image_key}' récupérée depuis le cache DB")
            # Stocker en cache mémoire pour accès futurs
            self._image_cache[image_key] = attachment.datas
            return attachment.datas

        # Générer l'image
        _logger.info(f"Génération d'une nouvelle image pour '{image_key}'")
        image_data = self._generate_default_image(image_key, naf_code)

        if image_data:
            # Stocker en cache mémoire
            self._image_cache[image_key] = image_data

            # Stocker en cache DB pour persistance
            self.env['ir.attachment'].sudo().create({
                'name': cache_name,
                'type': 'binary',
                'datas': image_data,
                'res_model': 'res.partner',
                'res_id': 0,
                'public': False,
                'description': f"Image cache pour catégorie: {image_key}",
            })

        return image_data

    @api.model
    def _generate_default_image(self, image_key, naf_code=None):
        """
        Génère une image par défaut basée sur la clé.
        À personnaliser selon votre logique de génération.

        :param image_key: Type d'image à générer
        :param naf_code: Code NAF optionnel
        :return: Image encodée en base64
        """
        try:
            # Exemple: utiliser tools.image_colorize ou une autre méthode
            from odoo import tools
            import io
            from PIL import Image, ImageDraw, ImageFont

            # Créer une image simple avec une couleur de fond selon la catégorie
            colors = {
                'sport': '#FF6B6B',
                'commerce': '#4ECDC4',
                'industrie': '#95E1D3',
                'service': '#FFE66D',
                'default': '#C7CEEA',
            }

            color = colors.get(image_key.lower(), colors['default'])

            # Créer une image 512x512
            img = Image.new('RGB', (512, 512), color)
            draw = ImageDraw.Draw(img)

            # Ajouter un texte simple
            try:
                # Essayer avec une police système
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            except:
                font = ImageFont.load_default()

            # Centrer le texte
            text = image_key[:1].upper()
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            position = ((512 - text_width) / 2, (512 - text_height) / 2)

            draw.text(position, text, fill='white', font=font)

            # Convertir en base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_data = base64.b64encode(buffer.getvalue())

            return img_data

        except Exception as e:
            _logger.error(f"Erreur lors de la génération de l'image '{image_key}': {e}")
            return False

    @api.model
    def _get_image_key_from_tags(self, partner):
        """
        Détermine la clé d'image basée sur les tags/NAF du partenaire.

        :param partner: Recordset res.partner
        :return: Clé d'image (str)
        """
        # Priorité aux tags APE
        ape_tags = partner.category_id.filtered(lambda t: t.parent_id.name == 'APE')
        if ape_tags:
            # Utiliser le premier tag APE comme clé
            tag_name = ape_tags[0].name.lower()

            # Mapper vers des catégories génériques
            if any(kw in tag_name for kw in ['sport', 'loisir', 'récréat']):
                return 'sport'
            elif any(kw in tag_name for kw in ['commerce', 'vente', 'magasin']):
                return 'commerce'
            elif any(kw in tag_name for kw in ['industrie', 'fabrication', 'manufactur']):
                return 'industrie'
            elif any(kw in tag_name for kw in ['service', 'conseil', 'assistance']):
                return 'service'

        # Utiliser le code NAF si disponible
        if hasattr(partner, 'x_naf') and partner.x_naf:
            naf = partner.x_naf[:2]  # 2 premiers caractères

            # Mapping NAF -> catégorie
            naf_mapping = {
                '01': 'agriculture',
                '02': 'agriculture',
                '10': 'industrie',
                '45': 'commerce',
                '47': 'commerce',
                '55': 'service',
                '56': 'service',
                '93': 'sport',
            }

            return naf_mapping.get(naf, 'default')

        return 'default'

    @classmethod
    def _auto_assign_image(cls, partner):
        """
        Assigne automatiquement une image au partenaire en utilisant le cache.
        Version optimisée qui réutilise les images déjà générées.

        :param partner: Recordset res.partner
        """
        if not partner or partner.image_1920:
            return

        try:
            # Déterminer la clé d'image
            image_key = cls._get_image_key_from_tags(partner.sudo(), partner)

            # Récupérer ou générer l'image (avec cache)
            naf_code = getattr(partner, 'x_naf', None)
            image_data = partner._get_cached_or_generate_image(image_key, naf_code)

            if image_data:
                partner.sudo().write({'image_1920': image_data})
                _logger.debug(f"Image '{image_key}' assignée au partenaire {partner.name}")

        except Exception as e:
            _logger.warning(f"Impossible d'assigner une image au partenaire {partner.name}: {e}")

    @api.model
    def clear_image_cache(self, cache_type='all'):
        """
        Vide le cache des images.

        :param cache_type: 'memory', 'db', ou 'all'
        """
        if cache_type in ('memory', 'all'):
            self._image_cache.clear()
            _logger.info("Cache mémoire des images vidé")

        if cache_type in ('db', 'all'):
            attachments = self.env['ir.attachment'].sudo().search([
                ('name', 'like', 'partner_image_cache_%'),
                ('res_model', '=', 'res.partner'),
                ('res_id', '=', 0),
            ])
            count = len(attachments)
            attachments.unlink()
            _logger.info(f"Cache DB des images vidé ({count} entrées supprimées)")

    @api.model
    def regenerate_image_cache(self, categories=None):
        """
        Pré-génère les images pour les catégories courantes.
        Utile pour initialiser le cache avant une grosse importation.

        :param categories: Liste des catégories à pré-générer (None = toutes)
        """
        if categories is None:
            categories = ['sport', 'commerce', 'industrie', 'service', 'default']

        _logger.info(f"Pré-génération du cache pour {len(categories)} catégories...")

        for category in categories:
            self._get_cached_or_generate_image(category)

        _logger.info("Cache pré-généré avec succès")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache généré',
                'message': f'{len(categories)} images pré-générées et mises en cache.',
                'type': 'success',
            },
        }


class ResPartnerImageCacheWizard(models.TransientModel):
    """Wizard pour gérer le cache des images"""
    _name = 'res.partner.image.cache.wizard'
    _description = 'Gestion du cache des images partenaires'

    action = fields.Selection([
        ('clear_memory', 'Vider le cache mémoire'),
        ('clear_db', 'Vider le cache base de données'),
        ('clear_all', 'Vider tout le cache'),
        ('regenerate', 'Régénérer le cache'),
    ], string='Action', required=True, default='clear_all')

    def execute_action(self):
        Partner = self.env['res.partner']

        if self.action == 'clear_memory':
            Partner.clear_image_cache('memory')
            message = 'Cache mémoire vidé avec succès'
        elif self.action == 'clear_db':
            Partner.clear_image_cache('db')
            message = 'Cache base de données vidé avec succès'
        elif self.action == 'clear_all':
            Partner.clear_image_cache('all')
            message = 'Tout le cache a été vidé avec succès'
        elif self.action == 'regenerate':
            Partner.regenerate_image_cache()
            message = 'Cache régénéré avec succès'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Succès',
                'message': message,
                'type': 'success',
            },
        }

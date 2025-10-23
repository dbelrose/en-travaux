# -*- coding: utf-8 -*-
import logging
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_tahiti = fields.Char("N° TAHITI", index=True)
    x_etablissement = fields.Char("N° Établissement (RTE)", index=True)
    x_forme_juridique = fields.Char("Forme juridique")
    x_naf = fields.Char("Code NAF/APE")
    x_effectif_classe = fields.Char("Classe d'effectifs")
    x_archipel = fields.Char("Archipel / Île")
    x_date_creation = fields.Date("Date de création (RTE)")
    x_rte_updated_at = fields.Datetime("Dernière maj RTE")
    #
    # _sql_constraints = [
    #     ("uniq_etablissement", "unique(x_etablissement)", "Le N° d'établissement RTE doit être unique."),
    # ]

    @staticmethod
    def _auto_assign_image_from_generator(partner):
        """
        Assigne une image au partenaire via ResPartnerImageGenerator.
        Cette méthode utilise Font Awesome pour générer automatiquement une icône.

        :param partner: Recordset res.partner
        :return: bool - True si image assignée
        """
        if not partner or partner.image_1920:
            return False

        if not partner.is_company:
            return False

        try:
            # Accéder à ResPartnerImageGenerator
            generator = partner.env['res.partner.image.generator']

            # Récupérer l'icône (unicode_char, color_hex, description)
            unicode_char, color_hex, description = partner.env['res.partner']._get_icon_for_activity(
                partner.name,
                partner.category_id
            )

            if not unicode_char or not color_hex:
                _logger.debug("Pas d'icône trouvée pour '%s'", partner.name)
                return False

            # Générer ou récupérer depuis cache
            image_data = generator.get_or_generate_image(unicode_char, color_hex)

            if image_data:
                partner.write({'image_1920': image_data})
                _logger.info(
                    "Image auto-assignée '%s' au partenaire '%s' (ID: %s): %s",
                    color_hex, partner.name, partner.id, description
                )
                return True
            else:
                _logger.warning("Impossible de générer l'image pour '%s'", partner.name)
                return False

        except Exception as e:
            _logger.warning("Erreur lors de l'auto-assignation d'image pour '%s': %s", partner.name, str(e))
            return False

    @api.model
    def action_clear_image_cache(self):
        """Vide le cache ET les images des partenaires"""
        # Vider le cache des icons générées
        attachments = self.env['ir.attachment'].sudo().search([
            ('name', 'like', 'partner_icon_%'),
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', 0),
        ])
        count = len(attachments)
        attachments.unlink()

        # Optionnel : Supprimer aussi les images existantes des partenaires
        # pour forcer la régénération
        partners = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('image_1920', '!=', False),
        ])
        partners.write({'image_1920': False})

        _logger.info("Cache et images partenaires vidés : %s icons en cache supprimées", count)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cache vidé',
                'message': f"{count} images en cache supprimées. Les images seront régénérées à la prochaine sync.",
                'type': 'success',
                'sticky': False,
            },
        }

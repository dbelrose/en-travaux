# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PartnerImageAssignWizard(models.TransientModel):
    _name = 'partner.image.assign.wizard'
    _description = 'Assistant d\'attribution automatique des images'

    mode = fields.Selection([
        ('all', 'Tous les partenaires sans image'),
        ('selection', 'Partenaires sélectionnés'),
    ], string='Mode', default='all', required=True)

    only_with_ape = fields.Boolean(
        string='Uniquement avec catégorie APE',
        default=True,
        help='Ne traiter que les partenaires ayant au moins une catégorie APE'
    )

    preview_count = fields.Integer(
        string='Nombre de partenaires concernés',
        compute='_compute_preview_count'
    )

    @api.depends('mode', 'only_with_ape')
    def _compute_preview_count(self):
        for wizard in self:
            domain = [
                ('is_company', '=', True),
                ('image_1920', '=', False),
            ]

            if wizard.only_with_ape:
                ape_parent = self.env['res.partner.category'].search([
                    ('name', '=', 'APE'),
                    ('parent_id', '=', False)
                ], limit=1)
                if ape_parent:
                    domain.append(('category_id.parent_id', '=', ape_parent.id))

            if wizard.mode == 'selection' and self.env.context.get('active_ids'):
                domain.append(('id', 'in', self.env.context.get('active_ids')))

            wizard.preview_count = self.env['res.partner'].search_count(domain)

    def action_assign_images(self):
        self.ensure_one()

        domain = [
            ('is_company', '=', True),
            ('image_1920', '=', False),
        ]

        if self.only_with_ape:
            ape_parent = self.env['res.partner.category'].search([
                ('name', '=', 'APE'),
                ('parent_id', '=', False)
            ], limit=1)
            if ape_parent:
                domain.append(('category_id.parent_id', '=', ape_parent.id))

        if self.mode == 'selection' and self.env.context.get('active_ids'):
            domain.append(('id', 'in', self.env.context.get('active_ids')))

        partners = self.env['res.partner'].search(domain)

        count = 0
        for partner in partners:
            if self.env['res.partner']._auto_assign_image(partner):
                count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attribution des images',
                'message': f"{count} images assignées sur {len(partners)} partenaires traités.",
                'type': 'success',
                'sticky': False,
            },
        }

from odoo import models, fields, api, _


class BookingImport(models.Model):
    _inherit = 'booking.import'

    # Ajout de statistiques par origine
    airbnb_reservations = fields.Integer(
        string='Réservations Airbnb',
        compute='_compute_origin_stats',
        store=True
    )
    booking_com_reservations = fields.Integer(
        string='Réservations Booking.com',
        compute='_compute_origin_stats',
        store=True
    )
    other_reservations = fields.Integer(
        string='Autres réservations',
        compute='_compute_origin_stats',
        store=True
    )

    @api.depends('line_ids.origin')
    def _compute_origin_stats(self):
        """Calcule les statistiques par origine"""
        for record in self:
            lines = record.line_ids
            record.airbnb_reservations = len(lines.filtered(lambda l: l.origin == 'airbnb'))
            record.booking_com_reservations = len(lines.filtered(lambda l: l.origin == 'booking.com'))
            record.other_reservations = len(lines.filtered(lambda l: l.origin == 'other'))

    def action_import_airbnb_pdf(self):
        """Action pour ouvrir l'assistant d'import PDF"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importer PDF Airbnb'),
            'view_mode': 'form',
            'res_model': 'airbnb.pdf.importer',
            'target': 'new',
            'context': {'default_import_id': self.id}
        }

    def _prepare_line_data(self, row):
        """
        Surcharge pour ajouter l'origine Booking.com
        Méthode héritée du module parent
        """
        result = super()._prepare_line_data(row)
        result['origin'] = 'booking.com'
        return result

    def action_view_reservations_by_origin(self):
        """Affiche les réservations groupées par origine"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Réservations par origine'),
            'res_model': 'booking.import.line',
            'view_mode': 'tree,form',
            'domain': [('import_id', '=', self.id)],
            'context': {'group_by': 'origin'},
            'target': 'current',
        }

    @api.model
    def create_manual_import(self, name=None):
        """Crée un import manuel pour saisie directe"""
        if not name:
            name = _("Import manuel %s") % fields.Datetime.now().strftime('%d/%m/%Y %H:%M')

        return self.create({
            'display_name': name,
            'import_type': 'manual',
            'import_date': fields.Datetime.now(),
            'state': 'draft',
        })

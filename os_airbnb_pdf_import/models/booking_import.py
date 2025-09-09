from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BookingImport(models.Model):
    _inherit = 'booking.import'

    # Ajout du champ pour le fichier PDF Airbnb (comme file_data pour Excel)
    pdf_file_data = fields.Binary(string='Fichier PDF Airbnb')
    pdf_filename = fields.Char(string='Nom du fichier PDF')

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
            lines = record.line_ids.filtered(lambda l: hasattr(l, 'origin'))
            record.airbnb_reservations = len(lines.filtered(lambda l: l.origin == 'airbnb'))
            record.booking_com_reservations = len(lines.filtered(lambda l: l.origin == 'booking.com'))
            record.other_reservations = len(lines.filtered(lambda l: l.origin == 'other'))

    def import_airbnb_pdf(self):
        """Importe les réservations depuis un fichier PDF Airbnb"""
        self.ensure_one()
        if not self.pdf_file_data:
            raise UserError(_("Aucun fichier PDF n'a été téléchargé."))

        try:
            # Créer et exécuter l'importateur PDF
            airbnb_importer = self.env['airbnb.pdf.importer'].create({
                'pdf_file': self.pdf_file_data,
                'pdf_filename': self.pdf_filename,
                'import_id': self.id,
            })

            # Exécuter l'import
            result = airbnb_importer.import_airbnb_pdf()

            # Mise à jour du statut
            self.state = 'imported'

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Import réussi'),
                    'message': _('Le fichier PDF Airbnb a été importé avec succès.'),
                    'type': 'success',
                    'sticky': False,
                },
            }

        except Exception as e:
            raise UserError(_("Erreur lors de l'importation: %s") % str(e))

    def _prepare_line_data(self, row):
        """Surcharge pour ajouter l'origine Booking.com"""
        result = super()._prepare_line_data(row)
        result['origin'] = 'booking.com'
        return result

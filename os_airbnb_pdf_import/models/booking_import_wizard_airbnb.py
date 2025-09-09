from odoo import models, fields, _
from odoo.exceptions import UserError


class BookingImportWizardAirbnb(models.TransientModel):
    _name = 'booking.import.wizard.airbnb'
    _description = 'Assistant d\'import Airbnb direct'

    pdf_file = fields.Binary(string='Fichier PDF Airbnb', required=True)
    pdf_filename = fields.Char(string='Nom du fichier')
    import_name = fields.Char(string='Nom de l\'import',
                              default=lambda self: f"Import Airbnb {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}")
    company_id = fields.Many2one('res.company', string='Société',
                                 default=lambda self: self.env.company, required=True)

    def import_airbnb_pdf_direct(self):
        """Importe directement un PDF Airbnb en créant un nouvel import"""
        if not self.pdf_file:
            raise UserError(_("Veuillez sélectionner un fichier PDF."))

        # Créer un nouvel import
        booking_import = self.env['booking.import'].create({
            'display_name': self.import_name,
            'import_type': 'manual',
            'import_date': fields.Datetime.now(),
            'state': 'draft',
            'company_id': self.company_id.id,
        })

        # Créer et exécuter l'importateur PDF
        airbnb_importer = self.env['airbnb.pdf.importer'].create({
            'pdf_file': self.pdf_file,
            'pdf_filename': self.pdf_filename,
            'import_id': booking_import.id,
        })

        # Exécuter l'import
        try:
            result = airbnb_importer.import_airbnb_pdf()

            # Mettre à jour le statut de l'import
            booking_import.state = 'imported'

            # Retourner vers l'import créé pour voir le résultat
            return {
                'type': 'ir.actions.act_window',
                'name': _('Import Airbnb terminé'),
                'view_mode': 'form',
                'res_model': 'booking.import',
                'res_id': booking_import.id,
                'target': 'current',
            }

        except Exception as e:
            # En cas d'erreur, supprimer l'import vide
            booking_import.unlink()
            raise UserError(_("Erreur lors de l'import: %s") % str(e))

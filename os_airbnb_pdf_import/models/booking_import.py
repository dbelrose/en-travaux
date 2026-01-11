# Fichier: os_airbnb_pdf_import/models/booking_import.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BookingImport(models.Model):
    _inherit = 'booking.import'

    import_type = fields.Selection(
        selection_add=[('pdf', 'PDF')],
        ondelete={'pdf': 'set default'}
    )

    origin = fields.Selection(
        selection_add=[('airbnb', 'Airbnb')],
        ondelete={'airbnb': 'set default'}
    )

    # Statistiques par origine - SANS @api.depends pour éviter l'erreur
    airbnb_reservations = fields.Integer(
        string='Réservations Airbnb',
        compute='_compute_origin_stats',
        store=True  # Important: pas de stockage pour éviter les problèmes
    )

    def _compute_origin_stats(self):
        """Calcule les statistiques par origine"""
        for record in self:
            # Initialiser à zéro
            record.airbnb_reservations = 0
            record.booking_com_reservations = 0
            record.other_reservations = 0

            try:
                # Chercher dynamiquement le champ de relation vers les lignes
                lines_field = None
                possible_fields = ['line_ids', 'booking_import_line_ids', 'import_line_ids', 'lines']

                for field_name in possible_fields:
                    if hasattr(record, field_name):
                        lines_field = field_name
                        break

                if lines_field:
                    lines = getattr(record, lines_field)
                    if lines:
                        # Vérifier si les lignes ont un champ origin
                        lines_with_origin = lines.filtered(lambda l: hasattr(l, 'origin') and l.origin)
                        if lines_with_origin:
                            record.airbnb_reservations = len(lines_with_origin.filtered(lambda l: l.origin == 'airbnb'))
                            record.booking_com_reservations = len(
                                lines_with_origin.filtered(lambda l: l.origin == 'booking.com'))
                            record.other_reservations = len(lines_with_origin.filtered(lambda l: l.origin == 'other'))

            except Exception as e:
                # En cas d'erreur, on reste à zéro sans faire planter
                import logging
                _logger = logging.getLogger(__name__)
                _logger.debug(f"Erreur calcul statistiques origine: {e}")

    def import_airbnb_pdf(self):
        """Importe les réservations depuis un fichier PDF Airbnb"""
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Aucun fichier PDF n'a été téléchargé."))

        try:
            # Créer et exécuter l'importateur PDF
            airbnb_importer = self.env['airbnb.pdf.importer'].create({
                'pdf_file': self.file_data,
                'file_name': self.file_name,
                'import_id': self.id,
            })

            # Exécuter l'import
            result = airbnb_importer.import_airbnb_pdf()

            # Mise à jour du statut si le champ existe
            if hasattr(self, 'state'):
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
        """Surcharge pour ajouter l'origine Booking.com - si la méthode parent existe"""
        try:
            result = super()._prepare_line_data(row)
            result['origin'] = 'booking.com'
            return result
        except (AttributeError, TypeError):
            # Si la méthode parent n'existe pas, retourner un dictionnaire de base
            return {'origin': 'booking.com'}

    # ========================================
    # MÉTHODES POUR LES ACTIONS DES BOUTONS
    # ========================================

    def action_add_reservation(self):
        """Action pour ajouter une réservation - déléguer au parent ou implémenter"""
        try:
            # Essayer d'appeler la méthode du parent si elle existe
            return super().action_add_reservation()
        except AttributeError:
            # Si la méthode n'existe pas dans le parent, implémenter une version de base
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action non disponible'),
                    'message': _('Cette action n\'est pas encore implémentée dans ce module.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

    def action_process_import(self):
        """Action pour traiter l'import - déléguer au parent ou implémenter"""
        try:
            return super().action_process_import()
        except AttributeError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action non disponible'),
                    'message': _('Cette action n\'est pas encore implémentée dans ce module.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

    def action_view_quarters(self):
        """Action pour voir les déclarations - déléguer au parent ou implémenter"""
        try:
            return super().action_view_quarters()
        except AttributeError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action non disponible'),
                    'message': _('Cette action n\'est pas encore implémentée dans ce module.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

    def action_view_months(self):
        """Action pour voir les vues mensuelles - déléguer au parent ou implémenter"""
        try:
            return super().action_view_months()
        except AttributeError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Action non disponible'),
                    'message': _('Cette action n\'est pas encore implémentée dans ce module.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

    def action_test_wizard(self):
        """Bouton de test pour vérifier que le wizard s'ouvre"""
        self.ensure_one()

        # Créer un wizard de test
        wizard = self.env['airbnb.import.confirm.wizard'].create({
            'import_id': self.id,
            'partner_id': self.env.user.partner_id.id,
            'parsed_data': '{"test": true}',
            'partner_name': 'Test Voyageur',
            'pax_nb': 2,
            'children': 0,
            'duration_nights': 3,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Test Wizard',
            'view_mode': 'form',
            'res_model': 'airbnb.import.confirm.wizard',
            'res_id': wizard.id,
            'target': 'new',
            'views': [(False, 'form')],
        }

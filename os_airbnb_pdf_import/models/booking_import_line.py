# Fichier: os_airbnb_pdf_import/models/booking_import_line.py

from odoo import models, fields


class BookingImportLine(models.Model):
    _name = 'booking.import.line'
    _inherit = 'booking.import.line'

    # Ajout sécurisé du champ origin
    origin = fields.Selection([
        ('airbnb', 'Airbnb'),
        ('booking.com', 'Booking.com'),
        ('other', 'Autre'),
    ], string='Origine', default='other', help="Canal d'origine de la réservation")

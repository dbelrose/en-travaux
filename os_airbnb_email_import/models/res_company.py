# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import imaplib
import ssl


class ResCompany(models.Model):
    _inherit = 'res.company'

    # ============================================
    # CONFIGURATION IMAP AIRBNB
    # ============================================

    airbnb_imap_host = fields.Char(
        string='Serveur IMAP',
        help='Adresse du serveur IMAP (ex: mail.belroseplace.site)',
        default='mail.belroseplace.site'
    )

    airbnb_imap_port = fields.Integer(
        string='Port IMAP',
        help='Port du serveur IMAP (993 pour SSL)',
        default=993
    )

    airbnb_imap_user = fields.Char(
        string='Utilisateur IMAP',
        help='Adresse email complète (ex: contact@belroseplace.site)',
        default='contact@belroseplace.site'
    )

    airbnb_imap_password = fields.Char(
        string='Mot de passe IMAP',
        help='Mot de passe du compte email'
    )

    airbnb_imap_ssl = fields.Boolean(
        string='Utiliser SSL',
        default=True,
        help='Activer la connexion sécurisée SSL/TLS'
    )

    airbnb_auto_process = fields.Boolean(
        string='Traitement automatique',
        default=True,
        help='Traiter automatiquement les emails Airbnb reçus'
    )

    airbnb_imap_folder = fields.Char(
        string='Dossier IMAP',
        default='INBOX',
        help='Dossier à surveiller (INBOX par défaut)'
    )

    airbnb_sender_emails = fields.Char(
        string='Adresses expéditeurs',
        default='automated@airbnb.com',
        help='Adresses email à surveiller (séparées par des virgules). Ex: automated@airbnb.com,votreadresse@gmail.com'
    )

    airbnb_last_fetch = fields.Datetime(
        string='Dernière récupération',
        readonly=True,
        help='Date/heure de la dernière récupération des emails'
    )

    # ============================================
    # CONVERSION DEVISE
    # ============================================

    def get_eur_to_xpf_rate(self):
        """
        Retourne le taux de conversion EUR → XPF
        Basé sur : 1000 XPF = 8.38 EUR
        Donc : 1 EUR = 119.33 XPF
        """
        self.ensure_one()
        return 1000 / 8.38  # = 119.33

    def convert_eur_to_xpf(self, amount_eur):
        """Convertit un montant EUR en XPF"""
        self.ensure_one()
        rate = self.get_eur_to_xpf_rate()
        return amount_eur * rate

    # ============================================
    # TEST CONNEXION IMAP
    # ============================================

    def action_test_imap_connection(self):
        """Teste la connexion IMAP"""
        self.ensure_one()

        if not self.airbnb_imap_host or not self.airbnb_imap_user or not self.airbnb_imap_password:
            raise UserError(_("Veuillez configurer tous les paramètres IMAP."))

        try:
            # Connexion au serveur IMAP
            if self.airbnb_imap_ssl:
                context = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL(self.airbnb_imap_host, self.airbnb_imap_port, ssl_context=context)
            else:
                mail = imaplib.IMAP4(self.airbnb_imap_host, self.airbnb_imap_port)

            # Authentification
            mail.login(self.airbnb_imap_user, self.airbnb_imap_password)

            # Sélection du dossier
            mail.select(self.airbnb_imap_folder or 'INBOX')

            # Déconnexion
            mail.logout()

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Connexion réussie'),
                    'message': _('La connexion au serveur IMAP a été établie avec succès.'),
                    'type': 'success',
                    'sticky': False,
                },
            }

        except imaplib.IMAP4.error as e:
            raise UserError(_("Erreur IMAP : %s") % str(e))
        except Exception as e:
            raise UserError(_("Erreur de connexion : %s") % str(e))

    # ============================================
    # FETCH EMAILS
    # ============================================

    def action_fetch_airbnb_emails(self):
        """Récupère manuellement les emails Airbnb"""
        self.ensure_one()

        if not self.airbnb_auto_process:
            raise UserError(_("Le traitement automatique est désactivé pour cette société."))

        fetcher = self.env['airbnb.email.fetcher'].sudo()
        result = fetcher.fetch_emails_for_company(self.id)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('📧 Emails récupérés'),
                'message': _('%d email(s) Airbnb traité(s)') % result.get('processed', 0),
                'type': 'success' if result.get('processed', 0) > 0 else 'info',
                'sticky': False,
            },
        }

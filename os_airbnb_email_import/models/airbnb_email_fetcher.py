# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import imaplib
import email
from email.header import decode_header
import ssl
import logging

_logger = logging.getLogger(__name__)


class AirbnbEmailFetcher(models.TransientModel):
    _name = 'airbnb.email.fetcher'
    _description = 'Récupérateur d\'emails Airbnb'

    # ============================================
    # CRON JOB - TOUTES LES 15 MINUTES
    # ============================================

    @api.model
    def cron_fetch_all_companies(self):
        """
        Méthode appelée par le cron job
        Récupère les emails Airbnb pour toutes les sociétés actives
        """
        companies = self.env['res.company'].search([
            ('airbnb_auto_process', '=', True),
            ('airbnb_imap_host', '!=', False),
            ('airbnb_imap_user', '!=', False),
            ('airbnb_imap_password', '!=', False),
        ])

        total_processed = 0
        for company in companies:
            try:
                result = self.fetch_emails_for_company(company.id)
                total_processed += result.get('processed', 0)
                _logger.info(
                    f"📧 Société {company.name} : {result.get('processed', 0)} email(s) Airbnb traité(s)"
                )
            except Exception as e:
                _logger.error(f"❌ Erreur récupération emails pour {company.name} : {e}")

        _logger.info(f"✅ Cron Airbnb terminé : {total_processed} email(s) traité(s) au total")

    # ============================================
    # FETCH POUR UNE SOCIÉTÉ
    # ============================================

    def fetch_emails_for_company(self, company_id):
        """
        Récupère et traite les emails Airbnb pour une société donnée
        
        Returns:
            dict: {'processed': int, 'errors': int}
        """
        company = self.env['res.company'].browse(company_id)
        
        if not company.exists():
            raise UserError(_("Société introuvable."))

        processed = 0
        errors = 0

        try:
            # Connexion IMAP
            mail = self._connect_imap(company)

            # Sélection du dossier
            mail.select(company.airbnb_imap_folder or 'INBOX')

            # Recherche des emails Airbnb non lus
            status, messages = mail.search(None, '(FROM "automated@airbnb.com" UNSEEN)')

            if status != 'OK':
                _logger.warning(f"Aucun email trouvé pour {company.name}")
                mail.logout()
                return {'processed': 0, 'errors': 0}

            email_ids = messages[0].split()
            _logger.info(f"🔍 {len(email_ids)} email(s) non lu(s) trouvé(s) pour {company.name}")

            # Traitement de chaque email
            for email_id in email_ids:
                try:
                    # Récupération de l'email
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue

                    # Parsing de l'email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Traitement de l'email
                    self._process_email(msg, company)
                    processed += 1

                    # Marquer comme lu
                    mail.store(email_id, '+FLAGS', '\\Seen')

                except Exception as e:
                    _logger.error(f"❌ Erreur traitement email {email_id} : {e}")
                    errors += 1

            # Déconnexion
            mail.logout()

            # Mise à jour date dernière récupération
            company.write({'airbnb_last_fetch': fields.Datetime.now()})

        except Exception as e:
            _logger.error(f"❌ Erreur connexion IMAP pour {company.name} : {e}")
            errors += 1

        return {'processed': processed, 'errors': errors}

    # ============================================
    # CONNEXION IMAP
    # ============================================

    def _connect_imap(self, company):
        """Établit la connexion IMAP"""
        try:
            if company.airbnb_imap_ssl:
                context = ssl.create_default_context()
                mail = imaplib.IMAP4_SSL(
                    company.airbnb_imap_host,
                    company.airbnb_imap_port,
                    ssl_context=context
                )
            else:
                mail = imaplib.IMAP4(company.airbnb_imap_host, company.airbnb_imap_port)

            # Authentification
            mail.login(company.airbnb_imap_user, company.airbnb_imap_password)
            return mail

        except imaplib.IMAP4.error as e:
            raise UserError(_("Erreur IMAP pour %s : %s") % (company.name, str(e)))
        except Exception as e:
            raise UserError(_("Erreur de connexion pour %s : %s") % (company.name, str(e)))

    # ============================================
    # TRAITEMENT EMAIL
    # ============================================

    def _process_email(self, msg, company):
        """
        Traite un email Airbnb
        
        1. Crée un lead CRM
        2. Parse l'email HTML
        3. Crée la réservation
        4. Convertit le lead
        """
        # Extraction du sujet
        subject = self._decode_header(msg.get('Subject', ''))
        from_email = msg.get('From', '')
        date_received = msg.get('Date', '')

        _logger.info(f"📧 Traitement email : {subject}")

        # Extraction du corps HTML
        html_body = self._extract_html_body(msg)

        if not html_body:
            _logger.warning(f"⚠️ Aucun corps HTML trouvé dans l'email : {subject}")
            return

        # Création du log
        email_log = self.env['airbnb.email.log'].sudo().create({
            'company_id': company.id,
            'subject': subject,
            'from_email': from_email,
            'date_received': fields.Datetime.now(),
            'html_body': html_body,
            'state': 'processing',
        })

        try:
            # Parsing des données
            parser = self.env['airbnb.email.parser'].sudo()
            parsed_data = parser.parse_email_html(html_body, company)

            if not parsed_data:
                email_log.write({
                    'state': 'error',
                    'error_message': 'Impossible de parser l\'email'
                })
                return

            # Vérification doublon
            if self._is_duplicate(parsed_data.get('booking_reference'), company):
                _logger.info(f"⏭️ Email ignoré (doublon) : {parsed_data.get('booking_reference')}")
                email_log.write({
                    'state': 'duplicate',
                    'booking_reference': parsed_data.get('booking_reference'),
                })
                return

            # Création du lead CRM
            lead = self._create_crm_lead(parsed_data, company, email_log)

            # Traitement de la réservation
            processor = self.env['airbnb.email.processor'].sudo()
            booking_line = processor.process_reservation(parsed_data, company, lead)

            # Mise à jour du log
            email_log.write({
                'state': 'success',
                'booking_reference': parsed_data.get('booking_reference'),
                'booking_line_id': booking_line.id,
                'lead_id': lead.id,
            })

            _logger.info(f"✅ Email traité avec succès : {parsed_data.get('booking_reference')}")

        except Exception as e:
            _logger.error(f"❌ Erreur traitement email : {e}")
            email_log.write({
                'state': 'error',
                'error_message': str(e)
            })
            raise

    # ============================================
    # HELPERS
    # ============================================

    def _decode_header(self, header_text):
        """Décode un header d'email"""
        if not header_text:
            return ''
        
        decoded_parts = decode_header(header_text)
        decoded_string = ''
        
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_string += part
        
        return decoded_string

    def _extract_html_body(self, msg):
        """Extrait le corps HTML d'un email"""
        html_body = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except Exception:
                        continue
        else:
            if msg.get_content_type() == 'text/html':
                try:
                    html_body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except Exception:
                    pass

        return html_body

    def _is_duplicate(self, booking_reference, company):
        """Vérifie si la réservation existe déjà"""
        if not booking_reference:
            return False

        existing = self.env['booking.import.line'].sudo().search([
            ('booking_reference', '=', booking_reference),
            ('company_id', '=', company.id),
        ], limit=1)

        return bool(existing)

    def _create_crm_lead(self, parsed_data, company, email_log):
        """Crée un lead CRM depuis les données parsées"""
        guest_name = f"{parsed_data.get('first_name', '')} {parsed_data.get('last_name', '')}".strip()
        property_name = parsed_data.get('property_type', 'Logement')

        lead = self.env['crm.lead'].sudo().create({
            'name': f"Airbnb - {guest_name} - {property_name}",
            'type': 'opportunity',
            'company_id': company.id,
            'email_from': 'automated@airbnb.com',
            'description': f"""
Code de confirmation : {parsed_data.get('booking_reference', 'N/A')}
Arrivée : {parsed_data.get('arrival_date', 'N/A')}
Départ : {parsed_data.get('departure_date', 'N/A')}
Voyageurs : {parsed_data.get('pax_nb', 0)} adulte(s)
Montant : {parsed_data.get('rate_eur', 0)} EUR
            """,
            'expected_revenue': parsed_data.get('rate_eur', 0),
            'probability': 100,
            'stage_id': self.env.ref('os_airbnb_email_import.crm_stage_airbnb_new').id,
            'airbnb_confirmation_code': parsed_data.get('booking_reference'),
            'email_log_id': email_log.id,
        })

        return lead

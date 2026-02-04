# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import imaplib
import ssl
import logging
import mailparser

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

            # DEBUG: Compter tous les emails
            status_all, messages_all = mail.search(None, 'ALL')
            total_emails = len(messages_all[0].split()) if messages_all[0] else 0
            _logger.info(f"📊 Total emails dans {company.airbnb_imap_folder or 'INBOX'}: {total_emails}")

            # Construire la requête IMAP depuis les adresses configurées
            sender_emails = company.airbnb_sender_emails or 'automated@airbnb.com'
            sender_list = [email.strip() for email in sender_emails.split(',')]

            # Construire la requête OR pour IMAP
            if len(sender_list) == 1:
                search_query = f'(FROM "{sender_list[0]}")'
            else:
                from_queries = [f'(FROM "{addr}")' for addr in sender_list]
                search_query = '(OR ' + ' '.join(from_queries) + ')'

            _logger.info(f"🔍 Recherche emails de: {sender_emails}")

            status_airbnb, messages_airbnb = mail.search(None, search_query)
            airbnb_emails = len(messages_airbnb[0].split()) if messages_airbnb[0] else 0
            _logger.info(f"📊 Total emails Airbnb potentiels (lus + non lus): {airbnb_emails}")

            # Recherche des emails Airbnb non lus
            status, messages = mail.search(None, f'{search_query} UNSEEN')

            if status != 'OK':
                _logger.warning(f"⚠️ Erreur recherche emails pour {company.name}: {status}")
                mail.logout()
                return {'processed': 0, 'errors': 0}

            email_ids = messages[0].split()

            # Si aucun email non lu, vérifier s'il y a des emails lus récents (dernières 24h)
            if not email_ids and airbnb_emails > 0:
                _logger.info(f"ℹ️ Aucun email non lu, recherche emails récents (24h)...")
                import datetime
                yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%d-%b-%Y")
                status, messages = mail.search(None, f'{search_query} SINCE {yesterday}')
                if status == 'OK':
                    email_ids = messages[0].split()
                    _logger.info(f"📊 {len(email_ids)} email(s) Airbnb trouvé(s) dans les dernières 24h")

            _logger.info(f"🔍 {len(email_ids)} email(s) à traiter pour {company.name}")

            # Traitement de chaque email
            for email_id in email_ids:
                try:
                    # Récupération de l'email
                    status, msg_data = mail.fetch(email_id, '(RFC822)')

                    if status != 'OK':
                        continue

                    # Parsing de l'email avec mailparser
                    raw_email = msg_data[0][1]
                    parsed_mail = mailparser.parse_from_bytes(raw_email)

                    # DEBUG: Afficher l'expéditeur
                    from_addr = parsed_mail.from_[0][1] if parsed_mail.from_ else 'unknown'
                    _logger.info(f"📧 Email de: {from_addr}")

                    # Traitement de l'email
                    self._process_email(parsed_mail, company)
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

    def _process_email(self, parsed_mail, company):
        """
        Traite un email Airbnb parsé avec mailparser

        1. Crée un lead CRM
        2. Parse l'email HTML
        3. Crée la réservation
        4. Convertit le lead
        """
        # Extraction des informations avec mailparser
        subject = parsed_mail.subject or ''
        from_email = parsed_mail.from_[0][1] if parsed_mail.from_ else 'automated@airbnb.com'

        _logger.info(f"📧 Traitement email : {subject}")

        # Extraction du corps HTML (mailparser nettoie déjà le Quoted-Printable)
        html_body = parsed_mail.text_html[0] if parsed_mail.text_html else None

        if not html_body:
            _logger.warning(f"⚠️ Aucun corps HTML trouvé dans l'email : {subject}")
            return

        # IMPORTANT: Ajouter le sujet au début du HTML pour le parsing du nom
        html_with_subject = f"<subject>{subject}</subject>\n{html_body}"

        # Création du log
        email_log = self.env['airbnb.email.log'].sudo().create({
            'company_id': company.id,
            'subject': subject,
            'from_email': from_email,
            'date_received': fields.Datetime.now(),
            'html_body': html_body,  # HTML original sans le sujet
            'state': 'processing',
        })

        try:
            # Parsing des données (avec sujet inclus)
            parser = self.env['airbnb.email.parser'].sudo()
            parsed_data = parser.parse_email_html(html_with_subject, company)

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

            # Création du lead CRM (avec conversion EUR)
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
    # HELPERS - Plus besoin de decode_header et extract_html_body
    # ============================================

    def _is_duplicate(self, booking_reference, company):
        """
        Vérifie si la réservation existe déjà
        Recherche dans booking.import.line ET airbnb.email.log
        """
        if not booking_reference:
            return False

        # Vérifier dans les réservations
        existing_booking = self.env['booking.import.line'].sudo().search([
            ('booking_reference', '=', booking_reference),
            ('company_id', '=', company.id),
        ], limit=1)

        if existing_booking:
            _logger.info(f"⏭️ Doublon détecté (réservation) : {booking_reference}")
            return True

        # Vérifier dans les emails traités avec succès
        existing_log = self.env['airbnb.email.log'].sudo().search([
            ('booking_reference', '=', booking_reference),
            ('company_id', '=', company.id),
            ('state', '=', 'success'),
        ], limit=1)

        if existing_log:
            _logger.info(f"⏭️ Doublon détecté (email log) : {booking_reference}")
            return True

        return False

    def _create_crm_lead(self, parsed_data, company, email_log):
        """Crée un lead CRM depuis les données parsées"""
        guest_name = f"{parsed_data.get('first_name', '')} {parsed_data.get('last_name', '')}".strip()
        property_name = parsed_data.get('property_type', 'Logement')

        # Conversion EUR → XPF pour le revenu attendu
        rate_xpf = company.convert_eur_to_xpf(parsed_data.get('rate_eur', 0))

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
Montant : {rate_xpf:.2f} XPF ({parsed_data.get('rate_eur', 0):.2f} EUR)
            """,
            'expected_revenue': rate_xpf,  # En XPF
            'probability': 100,
            'stage_id': self.env.ref('os_airbnb_email_import.crm_stage_airbnb_new').id,
            'airbnb_confirmation_code': parsed_data.get('booking_reference'),
            'email_log_id': email_log.id,
        })

        return lead

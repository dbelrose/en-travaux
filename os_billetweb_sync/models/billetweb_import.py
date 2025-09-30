from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)


class BilletwebImport(models.Model):
    _name = 'billetweb.import'
    _description = 'Prévisualisation des virements BilletWeb à importer'

    payout_id = fields.Char(string="ID BilletWeb")
    date = fields.Date(string="Date")
    amount = fields.Monetary(string="Montant", currency_field='currency_id')
    account = fields.Char(string="Nom du compte")
    iban = fields.Char(string="IBAN")
    swift = fields.Char(string="SWIFT / BIC")
    currency_id = fields.Many2one('res.currency', string="Devise", default=lambda self: self.env.ref('base.EUR'))

    state = fields.Selection([
        ('new', 'Nouveau'),
        ('imported', 'Déjà importé'),
        ('error', 'Erreur'),
    ], default='new', string="État")

    def action_import_api(self):
        _logger = logging.getLogger(__name__)
        sync_service = self.env['billetweb.sync.service']
        processor = self.env['billetweb.sync.processor']

        _logger.info("[BilletWeb] Début import payout ➔ attendees ➔ Odoo")

        success_count = 0
        error_count = 0
        total_read = 0
        companies_processed = 0

        matrix = sync_service.get_api_matrix()

        if not matrix:
            _logger.warning("[BilletWeb] Aucune configuration trouvée pour importer.")

            # Si appelé depuis l'interface utilisateur, afficher un message
            if self.env.context.get('from_ui'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Import BilletWeb',
                        'message': 'Aucune configuration trouvée pour importer.',
                        'type': 'warning',
                        'sticky': False,
                    }
                }
            return

        for api_date, api_user, api_key in matrix:
            _logger.info(f"[BilletWeb] Traitement API_USER={api_user} DATE={api_date}")
            companies_processed += 1

            payout_lines = sync_service.call_api(api_user, api_key, api_date)
            total_read += len(payout_lines) if payout_lines else 0

            for payout_line in payout_lines:
                ext_id = payout_line['ext_id']

                if not ext_id:
                    _logger.warning("[BilletWeb] Virement sans ext_id, ignoré.")
                    continue

                attendee_info = sync_service.call_attendee_api(api_user, api_key, ext_id)

                if attendee_info:
                    # Chercher la bonne société (api_user = société = res.company)
                    company = sync_service.find_company(api_user)
                    if not company:
                        _logger.error(f"[BilletWeb] Société non trouvée pour {api_user}.")
                        continue

                    processor.process_payout_line(company, payout_line, attendee_info, api_user, api_key)
                    success_count += 1
                else:
                    _logger.warning(f"[BilletWeb] Aucun attendee pour ext_id={ext_id}")
                    error_count += 1

        _logger.info("[BilletWeb] Fin de l'import payout ➔ attendees ➔ Odoo")

        # Créer un enregistrement d'historique
        self.env['billetweb.import.history'].create({
            'company_id': self.env.company.id,
            'number_of_payouts': success_count,
            'number_of_errors': error_count,
            'status': 'success' if error_count == 0 else 'warning' if success_count else 'error',
            'log_message': 'Import automatique terminé.',
        })

        # Envoyer un mail de notification
        # Todo : à quoi correspond l'id
        # template = self.env.ref('os_billetweb_sync.mail_template_billetweb_import')
        # if template:
        #     template.sudo().send_mail(self.id, force_send=True)

        # 6. Facturation de commission
        self.env['billetweb.commission.invoice'].generate_commission_invoices()

        # Si appelé depuis l'interface utilisateur, afficher un résumé
        if self.env.context.get('from_ui'):
            # Déterminer le type de notification selon le résultat
            if error_count == 0 and success_count > 0:
                notification_type = 'success'
                title = 'Import BilletWeb - Succès'
            elif success_count > 0 and error_count > 0:
                notification_type = 'warning'
                title = 'Import BilletWeb - Avertissement'
            elif success_count == 0 and error_count > 0:
                notification_type = 'danger'
                title = 'Import BilletWeb - Erreur'
            else:
                notification_type = 'info'
                title = 'Import BilletWeb - Information'

            # Construire le message de résumé
            message = f"""
            <div>
                <strong>Résumé de l'import :</strong><br/>
                • Sociétés traitées : {companies_processed}<br/>
                • Enregistrements lus : {total_read}<br/>
                • Imports réussis : {success_count}<br/>
                • Erreurs : {error_count}
            </div>
            """

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': title,
                    'message': message,
                    'type': notification_type,
                    'sticky': True,  # Reste affiché jusqu'à ce que l'utilisateur le ferme
                }
            }
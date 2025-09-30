# models/billetweb_import_wizard.py
from odoo import models, fields
import logging


class BilletWebImportWizard(models.TransientModel):
    _name = 'billetweb.import.wizard'
    _description = 'Assistant Import BilletWeb'

    state = fields.Selection([
        ('start', 'Démarrage'),
        ('done', 'Terminé')
    ], default='start')

    # Champs pour le résumé
    companies_processed = fields.Integer('Sociétés traitées', readonly=True)
    records_read = fields.Integer('Enregistrements lus', readonly=True)
    success_count = fields.Integer('Imports réussis', readonly=True)
    error_count = fields.Integer('Erreurs', readonly=True)
    status = fields.Selection([
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur')
    ], string='Statut', readonly=True)

    def action_start_import(self):
        """Lance l'import et affiche les résultats"""
        _logger = logging.getLogger(__name__)
        sync_service = self.env['billetweb.sync.service']
        processor = self.env['billetweb.sync.processor']

        _logger.info("[BilletWeb] Début import payout ➔ attendees ➔ Odoo")

        success_count = 0
        error_count = 0
        total_read = 0
        companies_processed = 0

        try:
            matrix = sync_service.get_api_matrix()

            if not matrix:
                _logger.warning("[BilletWeb] Aucune configuration trouvée pour importer.")
                self.write({
                    'state': 'done',
                    'status': 'error',
                    'companies_processed': 0,
                    'records_read': 0,
                    'success_count': 0,
                    'error_count': 1,
                })
                return self._return_wizard()

            for api_date, api_user, api_key in matrix:
                _logger.info(f"[BilletWeb] Traitement API_USER={api_user} DATE={api_date}")
                companies_processed += 1

                payout_records = sync_service.call_api(api_user, api_key, api_date)
                total_read += sum(len(p.payout_detail_ids) for p in payout_records)
                previous_price = 0.0

                for payout_record in payout_records:
                    for detail in payout_record.payout_detail_ids:
                        ext_id = detail.ext_id

                        if not ext_id:
                            _logger.warning("[BilletWeb] Virement sans ext_id, ignoré.")
                            continue

                        price = detail.price
                        if price == 0:
                            _logger.warning("[BilletWeb] Gratuit ignoré : {price}.")
                            continue

                        if price < 0:
                            previous_price = abs(price)
                            _logger.warning("[BilletWeb] Régularisation ignorée : {price}.")
                            continue

                        if price == previous_price:
                            _logger.warning("[BilletWeb] Montant régularisé ignoré : {price}.")
                            continue

                        previous_price = 0.0

                        attendee_info = sync_service.call_attendee_api(api_user, api_key, ext_id)

                        if attendee_info:
                            company = sync_service.find_company(api_user)
                            if not company:
                                _logger.error(f"[BilletWeb] Société non trouvée pour {api_user}.")
                                continue

                            processor.process_payout_line(company, detail, attendee_info, api_user, api_key)
                            success_count += 1
                        else:
                            _logger.warning(f"[BilletWeb] Aucun attendee pour ext_id={ext_id}")
                            error_count += 1

            _logger.info("[BilletWeb] Fin de l'import payout ➔ attendees ➔ Odoo")

            # Déterminer le statut avant la création de l'historique
            if error_count == 0 and success_count > 0:
                status = 'success'
            elif success_count > 0 and error_count > 0:
                status = 'warning'
            else:
                status = 'error'

            # Commit explicite avant les opérations post-traitement
            self.env.cr.commit()

            # Créer l'historique avec gestion d'erreur
            try:
                history_record = self.env['billetweb.import.history'].create({
                    'company_id': self.env.company.id,
                    'number_of_payouts': success_count,
                    'number_of_errors': error_count,
                    'status': status,
                    'log_message': 'Import manuel terminé.',
                })
                _logger.info(f"[BilletWeb] Historique créé avec ID: {history_record.id}")
            except Exception as e:
                _logger.error(f"[BilletWeb] Erreur lors de la création de l'historique: {e}")
                # Continuer malgré l'erreur d'historique

            # Envoyer le mail avec gestion d'erreur
            try:
                template = self.env.ref('os_billetweb_sync.mail_template_billetweb_import', raise_if_not_found=False)
                if template:
                    template.sudo().send_mail(self.env.uid, force_send=True)
                    _logger.info("[BilletWeb] Email de notification envoyé")
                else:
                    _logger.warning("[BilletWeb] Template d'email non trouvé")
            except Exception as e:
                _logger.error(f"[BilletWeb] Erreur lors de l'envoi de l'email: {e}")

            # Facturation avec gestion d'erreur
            try:
                self.env['billetweb.commission.invoice'].generate_commission_invoices()
                _logger.info("[BilletWeb] Factures de commission générées")
            except Exception as e:
                _logger.error(f"[BilletWeb] Erreur lors de la génération des factures: {e}")

            # Mettre à jour le wizard avec les résultats
            self.write({
                'state': 'done',
                'companies_processed': companies_processed,
                'records_read': total_read,
                'success_count': success_count,
                'error_count': error_count,
                'status': status,
            })

        except Exception as e:
            _logger.error(f"[BilletWeb] Erreur générale lors de l'import: {e}")
            # Rollback en cas d'erreur critique
            self.env.cr.rollback()

            self.write({
                'state': 'done',
                'companies_processed': companies_processed,
                'records_read': total_read,
                'success_count': success_count,
                'error_count': error_count + 1,
                'status': 'error',
            })

        return self._return_wizard()

    def _return_wizard(self):
        """Retourne la vue du wizard"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
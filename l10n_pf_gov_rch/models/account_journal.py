from odoo import models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def action_import_moves(self):
        """Action dynamique pour ouvrir l'assistant d'importation selon le code du journal"""
        journal_code = self.code.lower()

        try:
            if journal_code in ('ieom', 'ccpbq', 'pf', 'num'):
                return self.env.ref(f'l10n_pf_gov_rch.action_bank_statement_import_{journal_code}').read()[0]
            else:
                if journal_code != 'ard':
                    return self.env.ref('l10n_pf_gov_rch.action_bank_statement_import_atea').read()[0]
        except ValueError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': f'Action d\'importation non trouvée pour le journal {journal_code}',
                    'type': 'warning'
                }
            }

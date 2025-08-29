from odoo import models

import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def duplicate_order_line(self):
        for line in self:
            if line.order_id:
                line.copy({'order_id': line.order_id.id})

    # def _prepare_invoice_line(self, **optional_values):
    #     """
    #     Surcharge de la méthode pour utiliser account_budget_id
    #     comme account_id dans les lignes de facture
    #     """
    #     # Appel de la méthode parent pour récupérer les valeurs de base
    #     res = super(PurchaseOrderLine, self)._prepare_invoice_line(**optional_values)
    #
    #     # Debugging: afficher les valeurs actuelles
    #     _logger.info(f"=== DEBUG INVOICE LINE PREPARATION ===")
    #     _logger.info(f"Ligne de commande ID: {self.id}")
    #     _logger.info(f"Produit: {self.product_id.name}")
    #     _logger.info(f"Account_id original: {res.get('account_id')}")
    #     _logger.info(f"Account_budget_id disponible: {getattr(self, 'account_budget_id', 'CHAMP_INEXISTANT')}")
    #
    #     # Vérifier si le champ existe
    #     if hasattr(self, 'account_budget_id') and self.account_budget_id:
    #         old_account_id = res.get('account_id')
    #         res['account_id'] = self.account_budget_id.id
    #         _logger.info(f"✓ Modification effectuée: {old_account_id} -> {self.account_budget_id.id}")
    #         _logger.info(f"✓ Nouveau compte: {self.account_budget_id.code} - {self.account_budget_id.name}")
    #     else:
    #         _logger.warning(f"✗ account_budget_id non défini ou vide pour la ligne {self.id}")
    #
    #     _logger.info(f"=== FIN DEBUG ===")
    #     return res

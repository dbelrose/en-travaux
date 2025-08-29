from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.model
    def default_get(self, fields_list):
        """
        Définit les valeurs par défaut, y compris account_id depuis account_budget_id
        """
        res = super(AccountMoveLine, self).default_get(fields_list)

        # Si on a un purchase_line_id dans le contexte
        if self.env.context.get('default_purchase_line_id'):
            purchase_line = self.env['purchase.order.line'].browse(self.env.context['default_purchase_line_id'])
            if hasattr(purchase_line, 'account_budget_id') and purchase_line.account_budget_id:
                # Vérifier que le compte est compatible avec le type d'écriture
                if self._is_account_compatible(purchase_line.account_budget_id, res):
                    res['account_id'] = purchase_line.account_budget_id.id
                    _logger.info(f"Compte par défaut défini: {purchase_line.account_budget_id.code}")

        return res

    @api.model
    def create(self, vals_list):
        """
        CORRECTION: Appliquer la logique budget UNIQUEMENT sur les lignes de produit,
        PAS sur les lignes de contrepartie (fournisseur/client)
        """
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            # IMPORTANT: Seulement pour les lignes avec purchase_line_id ET qui n'ont pas de partner_id
            # Les lignes de contrepartie (401, 411) ont toujours un partner_id
            if (vals.get("purchase_line_id") and
                    not vals.get("partner_id") and  # ← CRUCIAL: éviter les lignes de contrepartie
                    not vals.get("account_id")):

                # Récupérer la ligne d'achat
                purchase_line = self.env['purchase.order.line'].browse(vals["purchase_line_id"])

                # Si elle a un compte budget, l'utiliser
                if (hasattr(purchase_line, 'account_budget_id') and
                        purchase_line.account_budget_id and
                        self._is_account_compatible_for_vals(purchase_line.account_budget_id, vals)):

                    vals["account_id"] = purchase_line.account_budget_id.id
                    _logger.info(f"Compte budget appliqué: {purchase_line.account_budget_id.code}")

                # Sinon fallback sur 902 si pas de compte
                elif not vals.get("account_id"):
                    account_902 = self.env['account.account'].search([('code', '=', '902')], limit=1)
                    if account_902:
                        vals["account_id"] = account_902.id
                        _logger.info("Compte 902 appliqué par défaut")

        return super().create(vals_list)

    def _is_account_compatible(self, account, default_vals):
        """
        Vérifie si un compte est compatible avec le type d'écriture
        """
        try:
            # Vérifier si c'est un compte de charge ou de produit selon le contexte
            move_type = self.env.context.get('default_move_type', 'entry')

            # Pour les factures fournisseurs, on veut des comptes de charges
            if move_type == 'in_invoice' and account.user_type_id.type not in ['expense', 'other']:
                _logger.warning(f"Compte {account.code} incompatible avec facture fournisseur")
                return False

            # Pour les factures clients, on veut des comptes de produits
            if move_type == 'out_invoice' and account.user_type_id.type not in ['income', 'other']:
                _logger.warning(f"Compte {account.code} incompatible avec facture client")
                return False

            return True
        except Exception as e:
            _logger.error(f"Erreur lors de la vérification de compatibilité du compte: {e}")
            return False

    def _is_account_compatible_for_vals(self, account, vals):
        """
        Vérifie la compatibilité d'un compte pour les valeurs données
        """
        try:
            # Récupérer le type de mouvement depuis les vals ou le contexte
            move_id = vals.get('move_id')
            if move_id:
                move = self.env['account.move'].browse(move_id)
                move_type = move.move_type
            else:
                move_type = self.env.context.get('default_move_type', 'entry')

            # Même logique de vérification
            if move_type == 'in_invoice' and account.user_type_id.type not in ['expense', 'other']:
                return False
            if move_type == 'out_invoice' and account.user_type_id.type not in ['income', 'other']:
                return False

            return True
        except Exception as e:
            _logger.error(f"Erreur lors de la vérification de compatibilité: {e}")
            return False


class AccountMove(models.Model):
    _inherit = 'account.move'

    def copy(self, default=None):
        """
        CORRECTION: Simplifier la copie pour éviter les déséquilibres
        """
        if default is None:
            default = {}

        # Log de debug de l'original
        _logger.info(f"Copie de la facture {self.name} (ID: {self.id})")

        # Laisser Odoo faire la copie standard
        # Il gère automatiquement l'équilibre des écritures
        new_move = super(AccountMove, self).copy(default)

        # Appliquer les comptes budget après la copie si nécessaire
        self._apply_budget_accounts_after_copy(new_move)

        _logger.info(f"Facture copiée vers {new_move.name} (ID: {new_move.id})")

        return new_move

    def _apply_budget_accounts_after_copy(self, new_move):
        """
        Applique les comptes budget après copie si nécessaire
        """
        try:
            for line in new_move.line_ids:
                # Seulement pour les lignes de produit (pas les contreparties)
                if (line.purchase_line_id and
                        not line.partner_id and  # Éviter les lignes fournisseur/client
                        hasattr(line.purchase_line_id, 'account_budget_id') and
                        line.purchase_line_id.account_budget_id):

                    budget_account = line.purchase_line_id.account_budget_id

                    # Vérifier la compatibilité
                    if self._check_account_compatibility(budget_account, new_move.move_type):
                        # Mettre à jour le compte
                        line.with_context(check_move_validity=False).write({
                            'account_id': budget_account.id
                        })
                        _logger.info(f"Compte budget appliqué sur copie: {budget_account.code}")

        except Exception as e:
            _logger.error(f"Erreur lors de l'application des comptes budget: {e}")

    def _check_account_compatibility(self, account, move_type):
        """
        Vérifie la compatibilité d'un compte avec le type de mouvement
        """
        try:
            if move_type == 'in_invoice' and account.user_type_id.type not in ['expense', 'other']:
                return False
            if move_type == 'out_invoice' and account.user_type_id.type not in ['income', 'other']:
                return False
            return True
        except Exception as e:
            _logger.error(f"Erreur vérification compatibilité: {e}")
            return False

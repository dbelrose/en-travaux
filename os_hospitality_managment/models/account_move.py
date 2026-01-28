# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def create_mirror_invoice(self, original_invoice_id):
        """
        Crée une facture miroir en inversant les rôles client/fournisseur,
        dans la société associée au partenaire de la facture d'origine.
        """
        # -- Récupérer la facture originale --
        if isinstance(original_invoice_id, int):
            original_invoice = self.browse(original_invoice_id)
        elif getattr(original_invoice_id, '_name', '') == 'account.move':
            original_invoice = original_invoice_id
        else:
            original_invoice = original_invoice_id[:1] if original_invoice_id else self.browse(0)

        _logger.info("=== DÉBUT CRÉATION FACTURE MIROIR ===")
        _logger.info(
            "Facture originale: ID=%s, Nom=%s, Type=%s, Société=%s",
            original_invoice.id,
            original_invoice.name,
            original_invoice.move_type,
            original_invoice.company_id.name
        )

        # -- Vérifications --
        if not original_invoice.exists():
            raise UserError(_("La facture avec l'ID %s n'existe pas.") % original_invoice_id)
        if original_invoice.state != 'posted':
            raise UserError(_("Seules les factures validées peuvent être dupliquées en miroir."))

        # Vérifier les lignes de la facture originale
        original_lines = original_invoice.invoice_line_ids
        # v17 : les lignes produit ont display_type='product' (mais on tolère False pour compat)
        product_lines = original_lines.filtered(lambda l: l.display_type in (False, 'product'))
        _logger.info(
            "Facture originale: %d lignes dont %d lignes produits",
            len(original_lines), len(product_lines)
        )
        for i, line in enumerate(original_lines):
            _logger.info(
                "  Ligne %d: display_type='%s', account_id=%s, product_id=%s, name='%s'",
                i, line.display_type or 'product',
                line.account_id.id if line.account_id else None,
                line.product_id.id if line.product_id else None,
                line.name[:50] if line.name else ''
            )

        if not product_lines:
            # Dernière chance : lignes avec compte et display_type compatible
            lines_with_account = original_lines.filtered(
                lambda l: l.account_id and l.display_type in [False, 'product']
            )
            if lines_with_account:
                _logger.info("Trouvé %d lignes avec compte comptable", len(lines_with_account))
                product_lines = lines_with_account
            else:
                raise UserError(
                    _("La facture originale ne contient aucune ligne de produit (toutes sont des sections/notes)")
                )

        # -- Déterminer le nouveau type de facture --
        move_type_mapping = {
            'out_invoice': 'in_invoice',
            'out_refund': 'in_refund',
            'in_invoice': 'out_invoice',
            'in_refund': 'out_refund',
        }
        if original_invoice.move_type not in move_type_mapping:
            raise UserError(_("Type de facture non supporté pour la création miroir."))
        new_move_type = move_type_mapping[original_invoice.move_type]
        _logger.info("Nouveau type de facture: %s", new_move_type)

        # -- Trouver la société du partenaire destinataire --
        partner_company = self.env['res.company'].sudo().search([
            ('partner_id', '=', original_invoice.partner_id.id)
        ], limit=1)
        if not partner_company:
            raise UserError(
                _("Le partenaire %s n'a pas de société associée. Impossible de créer une facture miroir.")
                % (original_invoice.partner_id.display_name,)
            )
        _logger.info("Société miroir trouvée: %s", partner_company.name)

        # -- Journal explicite dans la société miroir --
        journal_id = self._get_mirror_journal(partner_company, new_move_type)
        _logger.info("Journal utilisé: %s", journal_id)

        # -- Préparer les lignes produit (sans les créer encore) --
        line_cmds = []
        _logger.info("Traitement de %d lignes de la facture originale", len(original_invoice.invoice_line_ids))
        for i, line in enumerate(original_invoice.invoice_line_ids):
            _logger.info(
                "Ligne %d: display_type='%s', product=%s, quantity=%s, price_unit=%s, account=%s",
                i, line.display_type or 'product',
                line.product_id.name if line.product_id else 'None',
                line.quantity, line.price_unit,
                line.account_id.code if line.account_id else 'None'
            )
            # Sections / notes -> on les recrée telles quelles
            if line.display_type in ('line_section', 'line_note'):
                line_cmds.append((0, 0, {
                    'display_type': line.display_type,
                    'name': line.name,
                    'sequence': line.sequence,
                }))
                _logger.info("Ajout ligne section/note: %s", line.name)
                continue

            # Lignes "produit" (comptables)
            if not line.account_id:
                _logger.warning("Ligne %d ignorée: pas de compte comptable", i)
                continue

            line_name = line.name or (line.product_id.name if line.product_id else "Ligne sans description")

            # Compte miroir
            mirror_account_id = self._get_mirror_account_id(line.account_id, new_move_type, partner_company)
            if not mirror_account_id:
                # Fallback : comptes revenus/dépenses de la société miroir
                if new_move_type in ['out_invoice', 'out_refund']:
                    fallback_accounts = self.env['account.account'].sudo().search([
                        ('company_id', '=', partner_company.id),
                        ('account_type', 'in', ['income', 'income_other', 'asset_receivable'])
                    ])
                    fallback = fallback_accounts.filtered(
                        lambda a: a.account_type in ['income', 'income_other']
                    )[:1] or fallback_accounts[:1]
                else:
                    fallback_accounts = self.env['account.account'].sudo().search([
                        ('company_id', '=', partner_company.id),
                        ('account_type', 'in', ['expense', 'expense_direct_cost', 'liability_payable'])
                    ])
                    fallback = fallback_accounts.filtered(
                        lambda a: a.account_type in ['expense', 'expense_direct_cost']
                    )[:1] or fallback_accounts[:1]
                if not fallback:
                    raise UserError(
                        _("Aucun compte comptable trouvé dans la société %s pour le type %s")
                        % (partner_company.display_name, new_move_type)
                    )
                mirror_account_id = fallback.id
                _logger.info("Utilisation du compte fallback: %s", fallback.code)

            # Taxes miroir
            mirror_taxes = self._get_mirror_tax_ids(line.tax_ids, new_move_type, partner_company)
            _logger.info(
                "Taxes originales: %s -> Taxes miroir: %s",
                line.tax_ids.mapped('name'),
                self.env['account.tax'].browse(mirror_taxes).mapped('name')
            )

            # Prix avec conservation de la structure remise
            quantity = line.quantity or 1.0
            price_unit = line.price_unit or 0.0
            discount = line.discount or 0.0

            _logger.info("Prix conservé: unit=%s, discount=%s%%, qty=%s",
                         price_unit, discount, quantity)

            line_vals = {
                'display_type': 'product',  # v17 : nécessaire pour l'onglet Lignes de facture
                'name': line_name,
                'quantity': quantity,
                'price_unit': price_unit,  # Prix brut conservé
                'discount': discount,  # Remise conservée
                'account_id': mirror_account_id,
                'sequence': line.sequence,
            }

            if line.product_id:
                line_vals['product_id'] = line.product_id.id
            if line.product_uom_id:
                line_vals['product_uom_id'] = line.product_uom_id.id
            if mirror_taxes:
                line_vals['tax_ids'] = [(6, 0, mirror_taxes)]
            if line.analytic_distribution:
                line_vals['analytic_distribution'] = line.analytic_distribution

            _logger.info("Valeurs ligne miroir: %s", line_vals)
            line_cmds.append((0, 0, line_vals))

        _logger.info("Préparation terminée: %d commandes de ligne préparées", len(line_cmds))

        # Vérifier qu'on a au moins une ligne avec compte comptable
        account_lines = [cmd for cmd in line_cmds if cmd[0] == 0 and cmd[2].get('account_id')]
        if not account_lines:
            raise UserError(_("Aucune ligne comptable valide trouvée dans la facture originale"))

        try:
            # -- Création 1 étape : move + lignes --
            mirror_vals = {
                'move_type': new_move_type,
                'partner_id': original_invoice.company_id.partner_id.id,
                'invoice_date': original_invoice.invoice_date,
                'invoice_date_due': original_invoice.invoice_date_due,
                'invoice_payment_term_id': original_invoice.invoice_payment_term_id.id
                                          if original_invoice.invoice_payment_term_id else False,
                'currency_id': original_invoice.currency_id.id,
                'company_id': partner_company.id,
                'journal_id': journal_id,
                'ref': _("Facture miroir de %s") % (
                    original_invoice.name or original_invoice.ref or str(original_invoice.id)
                ),
                'narration': _("Facture miroir générée automatiquement à partir de %s") % (
                    original_invoice.name or str(original_invoice.id)
                ),
                'invoice_line_ids': line_cmds,  # injectées dès la création
            }

            _logger.info("Création facture miroir (1 étape) avec %d lignes pour la société %s",
                         len(line_cmds), partner_company.display_name)
            mirror_invoice = (self.env['account.move']
                              .with_company(partner_company)
                              .with_context(check_move_validity=False, default_move_type=new_move_type)
                              .sudo()
                              .create(mirror_vals))
            _logger.info("Facture créée: ID=%s, Nom=%s", mirror_invoice.id, mirror_invoice.name)

            # -- Vérifs & recalcul --
            _logger.info("Vérification de la facture créée...")
            mirror_invoice.invalidate_recordset()
            mirror_invoice_fresh = self.env['account.move'].sudo().browse(mirror_invoice.id)

            total_lines = len(mirror_invoice_fresh.invoice_line_ids)
            product_lines_new = mirror_invoice_fresh.invoice_line_ids.filtered(
                lambda l: l.display_type in (False, 'product')
            )
            _logger.info(
                "Facture miroir - Total lignes: %d, Lignes produits: %d",
                total_lines, len(product_lines_new)
            )
            _logger.info("... (debug) Toutes écritures line_ids: %d", len(mirror_invoice_fresh.line_ids))
            for l in mirror_invoice_fresh.line_ids:
                _logger.info(
                    "... (debug) line_id=%s, name=%r, display_type=%s, account=%s, debit=%s, credit=%s, balance=%s",
                    l.id, l.name, l.display_type,
                    l.account_id.code if l.account_id else None,
                    l.debit, l.credit, l.balance
                )

            if not product_lines_new:
                raise UserError(_("Aucune ligne de facture n'a pu être créée dans la facture miroir"))

            _logger.info("Recalcul des totaux...")
            # Pas de recalcul nécessaire - Odoo calcule automatiquement les totaux
            mirror_invoice_fresh.invalidate_recordset()
            _logger.info(
                "Montants finaux - HT: %s, TTC: %s",
                mirror_invoice_fresh.amount_untaxed, mirror_invoice_fresh.amount_total
            )

            # -- Lien avec facture source --
            if mirror_invoice_fresh.name and mirror_invoice_fresh.name != '/':
                ref_text = _(' - Facture miroir: %s') % mirror_invoice_fresh.name
                current_ref = original_invoice.ref or ''
                if ref_text not in current_ref:
                    original_invoice.sudo().write({'ref': current_ref + ref_text})

            _logger.info(
                "Facture miroir créée avec succès: ID=%s, Nom=%s, Total=%s",
                mirror_invoice_fresh.id, mirror_invoice_fresh.name, mirror_invoice_fresh.amount_total
            )
            _logger.info("=== FIN CRÉATION FACTURE MIROIR ===")
            return mirror_invoice_fresh.id

        except Exception as e:
            _logger.exception("ERREUR CRÉATION FACTURE MIROIR")
            raise UserError(_("Erreur lors de la création de la facture miroir: %s") % str(e))

    def _get_mirror_account_id(self, original_account, new_move_type, partner_company):
        """
        Détermine le compte comptable approprié pour la facture miroir
        """
        # Rechercher d'abord un compte avec le même code
        mirror_account = self.env['account.account'].sudo().search([
            ('code', '=', original_account.code),
            ('company_id', '=', partner_company.id)
        ], limit=1)
        if mirror_account and mirror_account.account_type not in ['asset_receivable', 'liability_payable']:
            return mirror_account.id

        # Chercher par code similaire (éviter receivable/payable)
        base_code = original_account.code[:6] if len(original_account.code) >= 6 else original_account.code[:3]
        similar_account = self.env['account.account'].sudo().search([
            ('code', '=like', base_code + '%'),
            ('company_id', '=', partner_company.id),
            ('account_type', '=', original_account.account_type),
            ('account_type', 'not in', ['asset_receivable', 'liability_payable'])  # Éviter ces types
        ], limit=1)
        if similar_account:
            return similar_account.id

        # Compte par défaut selon le type (JAMAIS receivable/payable pour les lignes produit)
        if new_move_type in ['out_invoice', 'out_refund']:
            # Toujours utiliser un compte de revenus pour les factures de vente
            default_account = self.env['account.account'].sudo().search([
                ('company_id', '=', partner_company.id),
                ('account_type', '=', 'income'),
                ('code', '=like', '7%')
            ], limit=1)
            if not default_account:
                # Fallback sur income_other
                default_account = self.env['account.account'].sudo().search([
                    ('company_id', '=', partner_company.id),
                    ('account_type', '=', 'income_other')
                ], limit=1)
        else:
            # Toujours utiliser un compte de charges pour les factures d'achat
            default_account = self.env['account.account'].sudo().search([
                ('company_id', '=', partner_company.id),
                ('account_type', '=', 'expense'),
                ('code', '=like', '6%')
            ], limit=1)
            if not default_account:
                # Fallback sur expense_direct_cost
                default_account = self.env['account.account'].sudo().search([
                    ('company_id', '=', partner_company.id),
                    ('account_type', '=', 'expense_direct_cost')
                ], limit=1)

        return default_account.id if default_account else None

    def _get_mirror_tax_ids(self, original_taxes, new_move_type, partner_company):
        """
        Détermine les taxes appropriées pour la facture miroir
        """
        mirror_tax_ids = []
        tax_use = 'sale' if new_move_type in ['out_invoice', 'out_refund'] else 'purchase'
        for tax in original_taxes:
            # Chercher par nom
            mirror_tax = self.env['account.tax'].sudo().search([
                ('name', '=', tax.name),
                ('company_id', '=', partner_company.id),
                ('type_tax_use', '=', tax_use)
            ], limit=1)
            # Chercher par taux si pas trouvé par nom
            if not mirror_tax:
                mirror_tax = self.env['account.tax'].sudo().search([
                    ('amount', '=', tax.amount),
                    ('amount_type', '=', tax.amount_type),
                    ('company_id', '=', partner_company.id),
                    ('type_tax_use', '=', tax_use)
                ], limit=1)
            if mirror_tax:
                mirror_tax_ids.append(mirror_tax.id)
        return mirror_tax_ids

    def _get_mirror_journal(self, partner_company, new_move_type):
        """Retourne le journal 'sale' ou 'purchase' de la société miroir."""
        jt = 'sale' if new_move_type in ('out_invoice', 'out_refund') else 'purchase'
        journal = self.env['account.journal'].sudo().search([
            ('type', '=', jt),
            ('company_id', '=', partner_company.id)
        ], limit=1)
        if not journal:
            raise UserError(_("Aucun journal '%s' trouvé pour la société %s") % (jt, partner_company.display_name))
        return journal.id

    @api.model
    def create_mirror_invoice_wizard(self, invoice_id):
        """
        Méthode wrapper pour utilisation dans un wizard/action
        """
        try:
            # Diagnostic préalable
            self.diagnose_mirror_creation(invoice_id)
            mirror_id = self.create_mirror_invoice(invoice_id)
            mirror_invoice = self.browse(mirror_id)
            return {
                'type': 'ir.actions.act_window',
                'name': _('Facture Miroir Créée'),
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': mirror_id,
                'target': 'current',
                'context': {
                    'default_move_type': mirror_invoice.move_type,
                }
            }
        except Exception as e:
            _logger.exception("Erreur dans wizard de création facture miroir")
            raise UserError(str(e))

    @api.model
    def diagnose_mirror_creation(self, invoice_id):
        """
        Méthode de diagnostic pour identifier les problèmes potentiels
        """
        _logger.info("=== DIAGNOSTIC CRÉATION FACTURE MIROIR ===")
        invoice = self.browse(invoice_id)
        if not invoice.exists():
            raise UserError(_("Facture introuvable: %s") % invoice_id)
        _logger.info("Facture: %s (%s) - %s", invoice.name, invoice.state, invoice.move_type)

        # Vérifier les lignes
        lines = invoice.invoice_line_ids
        product_lines = lines.filtered(lambda l: l.display_type in (False, 'product'))
        lines_with_account = lines.filtered(lambda l: l.account_id and l.display_type in [False, 'product'])
        _logger.info(
            "Lignes: %d total, %d produits standard, %d avec compte",
            len(lines), len(product_lines), len(lines_with_account)
        )
        for i, line in enumerate(lines):
            _logger.info(
                "  Ligne %d: display_type='%s' \n account=%s \n product=%s \n name='%s'",
                i, line.display_type or 'product',
                line.account_id.code if line.account_id else 'None',
                line.product_id.name if line.product_id else 'None',
                (line.name[:50] + '...') if line.name and len(line.name) > 50 else line.name or ''
            )

        # Vérifier société partenaire
        partner_company = self.env['res.company'].sudo().search([
            ('partner_id', '=', invoice.partner_id.id)
        ], limit=1)
        if partner_company:
            _logger.info("Société partenaire: %s (ID: %s)", partner_company.name, partner_company.id)
            # Vérifier journaux
            sale_journals = self.env['account.journal'].sudo().search([
                ('type', '=', 'sale'),
                ('company_id', '=', partner_company.id)
            ])
            purchase_journals = self.env['account.journal'].sudo().search([
                ('type', '=', 'purchase'),
                ('company_id', '=', partner_company.id)
            ])
            _logger.info("Journaux vente: %s", sale_journals.mapped('name'))
            _logger.info("Journaux achat: %s", purchase_journals.mapped('name'))

            # Vérifier comptes
            income_accounts = self.env['account.account'].sudo().search([
                ('company_id', '=', partner_company.id),
                ('account_type', 'in', ['income', 'income_other'])
            ])
            expense_accounts = self.env['account.account'].sudo().search([
                ('company_id', '=', partner_company.id),
                ('account_type', 'in', ['expense', 'expense_direct_cost'])
            ])
            _logger.info("Comptes revenus: %s", income_accounts.mapped('code')[:5])
            _logger.info("Comptes charges: %s", expense_accounts.mapped('code')[:5])
        else:
            _logger.error("Aucune société trouvée pour le partenaire: %s", invoice.partner_id.name)

        _logger.info("=== FIN DIAGNOSTIC ===")
        return True

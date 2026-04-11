from odoo import _, api, fields, models
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

CREDIT_ALERT_THRESHOLDS = [20, 10, 5, 1]


class ResCompany(models.Model):
    _inherit = "res.company"

    pdf_print_credits = fields.Integer(
        string="Crédits d'impression PDF",
        default=0,
        help="Nombre d'impressions PDF restantes pour cette société.",
    )

    def _check_and_consume_print_credit(self):
        self.ensure_one()
        if self.pdf_print_credits <= 0:
            raise UserError(
                _(
                    "⛔ Votre société n'a plus de crédits d'impression PDF disponibles.\n\n"
                    "Veuillez réapprovisionner votre stock d'impressions avant de continuer.\n"
                    "Contactez votre administrateur ou créez un bon de commande depuis le menu "
                    "«\u202fPDF Report → Réapprovisionner les crédits\u202f»."
                )
            )

        self.env.cr.execute(
            "UPDATE res_company SET pdf_print_credits = pdf_print_credits - 1 "
            "WHERE id = %s AND pdf_print_credits > 0 RETURNING pdf_print_credits",
            (self.id,),
        )
        result = self.env.cr.fetchone()
        if not result:
            raise UserError(
                _(
                    "⛔ Votre société n'a plus de crédits d'impression PDF disponibles.\n\n"
                    "Veuillez réapprovisionner votre stock d'impressions."
                )
            )

        remaining = result[0]
        self.invalidate_recordset(["pdf_print_credits"])

        warning_message = None
        if remaining == 0:
            warning_message = _(
                "⚠️ ATTENTION : C'était votre dernier crédit d'impression PDF !\n"
                "Vous ne pourrez plus imprimer jusqu'au réapprovisionnement.\n"
                "Créez un bon de commande dès maintenant."
            )
        elif remaining in CREDIT_ALERT_THRESHOLDS:
            warning_message = _(
                "⚠️ Attention : il ne vous reste que %(count)d crédit(s) d'impression PDF.\n"
                "Pensez à réapprovisionner votre stock prochainement.",
                count=remaining,
            )

        if warning_message:
            _logger.warning(
                "PDF Print Credits warning for company %s (id=%s): %d credits remaining.",
                self.name, self.id, remaining,
            )

        return remaining, warning_message

    def action_add_print_credits(self, qty):
        self.ensure_one()
        if qty <= 0:
            raise UserError(_("La quantité à ajouter doit être supérieure à 0."))
        self.sudo().pdf_print_credits += qty
        _logger.info(
            "Added %d PDF print credits to company %s (id=%s). New total: %d.",
            qty, self.name, self.id, self.pdf_print_credits,
        )

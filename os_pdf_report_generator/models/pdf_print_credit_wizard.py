from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PdfPrintCreditWizard(models.TransientModel):
    _name = "pdf.print.credit.wizard"
    _description = "Assistant de réapprovisionnement de crédits d'impression PDF"

    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )
    current_credits = fields.Integer(
        string="Crédits actuels",
        compute="_compute_current_credits",
    )
    qty = fields.Integer(
        string="Quantité de crédits à ajouter",
        required=True,
        default=100,
        help="Nombre de crédits d'impression PDF à ajouter au stock de la société.",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Produit",
        compute="_compute_product_id",
        help="Produit utilisé pour la facturation des crédits d'impression.",
    )
    create_sale_order = fields.Boolean(
        string="Créer un bon de commande",
        default=False,
        help="Crée automatiquement un bon de commande pour ce réapprovisionnement.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Client (pour le devis)",
        help="Client à utiliser sur le bon de commande.",
    )
    note = fields.Text(
        string="Note interne",
        help="Note à ajouter au bon de commande.",
    )

    @api.depends("company_id")
    def _compute_current_credits(self):
        for rec in self:
            rec.current_credits = rec.company_id.pdf_print_credits if rec.company_id else 0

    @api.depends("company_id")
    def _compute_product_id(self):
        product = self.env.ref(
            "os_pdf_report_generator.product_pdf_print_credit",
            raise_if_not_found=False,
        )
        for rec in self:
            rec.product_id = product

    def action_add_credits(self):
        """Ajoute les crédits directement sans bon de commande."""
        self.ensure_one()
        self.company_id.action_add_print_credits(self.qty)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Crédits ajoutés"),
                "message": _(
                    "%(qty)d crédit(s) d'impression PDF ont été ajoutés à la société «\u202f%(company)s\u202f».\n"
                    "Nouveau solde : %(total)d crédit(s).",
                    qty=self.qty,
                    company=self.company_id.name,
                    total=self.company_id.pdf_print_credits,
                ),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_create_sale_order(self):
        """Crée un bon de commande pour le réapprovisionnement (sans ajouter les crédits)."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Veuillez sélectionner un client pour créer le bon de commande."))
        if not self.product_id:
            raise UserError(_("Le produit «\u202fCrédit d'impression PDF\u202f» est introuvable."))

        order = self.env["sale.order"].create({
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "note": self.note or "",
            "order_line": [(0, 0, {
                "product_id": self.product_id.id,
                "product_uom_qty": self.qty,
                "name": _(
                    "Crédits d'impression PDF — société : %(company)s",
                    company=self.company_id.name,
                ),
            })],
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Bon de commande"),
            "res_model": "sale.order",
            "res_id": order.id,
            "view_mode": "form",
            "target": "current",
        }

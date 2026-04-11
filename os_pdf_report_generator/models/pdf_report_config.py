from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PdfReportConfig(models.Model):
    _name = "pdf.report.config"
    _description = "PDF Report Configuration"

    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Report Name",
        required=True,
        readonly=True,
        help="Name of the report",
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        ondelete="cascade",
        readonly=True,
        help="Model to which this report will be attached",
    )
    field_id = fields.Many2one(
        "ir.model.fields",
        string="Field Name",
        required=True,
        ondelete="cascade",
        domain="[('model_id', '=', model_id),('ttype', '=', 'char')]",
        readonly=True,
        help="Field to be used as the report name",
    )
    report_pdf_template = fields.Binary(
        string="Report PDF Template",
        required=True,
        readonly=True,
        help="PDF template to be used for the report",
    )
    report_pdf_template_filename = fields.Char(
        string="Report PDF Template Name",
        required=True,
        readonly=True,
    )
    prefix = fields.Char(
        string="Prefix",
        readonly=True,
        help="Prefix to be used in the report name",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        string="State",
        default="draft",
        tracking=True,
        copy=False,
        readonly=True,
    )
    action_report_id = fields.Many2one(
        "ir.actions.report", string="Related Report Action", readonly=True, copy=False
    )

    print_report_name = fields.Char(
        string="Print Report Name",
        compute="_compute_print_report_name",
        help="Filename generated for the report",
    )

    # Champ stocké, rempli dans create() — depends("id") interdit dans Odoo 17
    technical_report_name = fields.Char(
        string="Nom technique du rapport",
        readonly=True,
        copy=False,
        help=(
            "Nom technique stable utilisable dans un bouton d'impression XML.\n"
            "Valeur : os_pdf_report_generator.pdf_report_{id}"
        ),
    )

    def _auto_init(self):
        """
        Crée la colonne technical_report_name si absente et la remplit
        rétroactivement pour les enregistrements existants.
        S'exécute à chaque démarrage, sans nécessiter de -u.
        """
        res = super()._auto_init()
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'pdf_report_config'
              AND column_name = 'technical_report_name'
        """)
        if not self.env.cr.fetchone():
            _logger.info(
                "_auto_init: colonne pdf_report_config.technical_report_name absente, création..."
            )
            self.env.cr.execute("""
                ALTER TABLE pdf_report_config
                ADD COLUMN technical_report_name VARCHAR
            """)
        # Remplir les enregistrements existants sans valeur
        self.env.cr.execute("""
            UPDATE pdf_report_config
            SET technical_report_name = 'os_pdf_report_generator.pdf_report_' || id::text
            WHERE technical_report_name IS NULL OR technical_report_name = ''
        """)
        return res

    @api.depends("model_id", "field_id", "prefix")
    def _compute_print_report_name(self):
        for rec in self:
            if rec.prefix:
                rec.print_report_name = (
                    f"'{rec.prefix} %s' % object.{rec.field_id.name} "
                    f"if object.{rec.field_id.name} else ''"
                )
            else:
                rec.print_report_name = (
                    f"'{rec.model_id.name} %s' % object.{rec.field_id.name} "
                    f"if object.{rec.field_id.name} else ''"
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.technical_report_name = rec._prepare_template_name()
        return records

    @api.constrains("report_pdf_template_filename")
    def _check_report_pdf_template_filename(self):
        for rec in self:
            if not rec.report_pdf_template_filename.endswith(".pdf"):
                raise UserError("Please upload a PDF template.")

    def _action_publish(self):
        for record in self:
            if record.state == "draft":
                val = record._prepare_action_val()
                if not record.action_report_id:
                    action_report = self.env["ir.actions.report"].sudo().create(val)
                else:
                    action_report = record.action_report_id
                    action_report.sudo().write(val)

                # Rattacher le binding au modèle cible (model_id), pas à pdf.report.config
                action_report.sudo().write({
                    "binding_model_id": record.model_id.id,
                    "binding_type": "report",
                })

                record.action_report_id = action_report
                record.state = "published"

                # Créer l'entrée ir.model.data pour l'external ID
                xmlid = f"pdf_report_{record.id}"
                existing = self.env["ir.model.data"].sudo().search([
                    ("module", "=", "os_pdf_report_generator"),
                    ("name", "=", xmlid),
                ])
                if not existing:
                    self.env["ir.model.data"].sudo().create({
                        "module": "os_pdf_report_generator",
                        "name": xmlid,
                        "model": "ir.actions.report",
                        "res_id": action_report.id,
                        "noupdate": True,
                    })
                record.technical_report_name = f"os_pdf_report_generator.{xmlid}"
            else:
                raise UserError("Report already published")
        return True

    def action_publish(self):
        self._action_publish()
        return self._refresh_page()

    def _action_unpublish(self):
        for record in self:
            if record.state == "published":
                # Supprimer l'entrée ir.model.data
                xmlid = f"pdf_report_{record.id}"
                self.env["ir.model.data"].sudo().search([
                    ("module", "=", "os_pdf_report_generator"),
                    ("name", "=", xmlid),
                ]).unlink()
                record.action_report_id.unlink_action()
                record.state = "draft"
            else:
                raise UserError("Report already unpublished")
        return True

    def action_unpublish(self):
        self._action_unpublish()
        return self._refresh_page()

    def _prepare_action_val(self):
        return {
            "name": self.name,
            "model": self.model_id.model,
            "report_type": "pdf",
            "report_pdf_template": self.report_pdf_template,
            "report_pdf_template_name": self.report_pdf_template_filename,
            "report_name": self._prepare_template_name(),
            "print_report_name": self.print_report_name,
        }

    def _prepare_template_name(self):
        """
        Nom déterministe basé sur l'ID — stable, lisible, sans collision.
        Remplace l'ancien SHA256 aléatoire.
        """
        return f"os_pdf_report_generator.pdf_report_{self.id}"

    @api.ondelete(at_uninstall=False)
    def _unlink_pdf_report(self):
        for rec in self:
            if rec.state == "published":
                rec.action_unpublish()
            if rec.action_report_id:
                rec.action_report_id.unlink()

    def _refresh_page(self):
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

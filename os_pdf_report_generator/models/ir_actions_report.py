import base64
import pdfrw
from datetime import datetime
from io import BytesIO
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


def _fill_pdf(template_pdf, doc_obj, data, context):
    _logger.info("Début du remplissage du PDF")
    for page_number, page in enumerate(template_pdf.pages):
        _logger.info(f"Traitement de la page {page_number + 1}")
        annotations = page.get('/Annots')
        if annotations:
            for annotation in annotations:
                key = annotation.get('/T')
                if key:
                    field_name = key[1:-1]
                    _logger.info(f"Annotation trouvée : {field_name}")
                    if field_name in data:
                        _logger.info(f"Remplissage du champ {field_name} avec la valeur {data[field_name]}")
                        annotation.update(pdfrw.PdfDict(V=data[field_name]))
                    else:
                        _logger.warning(f"Champ {field_name} non trouvé dans les données")
        else:
            _logger.warning(f"Aucune annotation trouvée sur la page {page_number + 1}")

    temp_output = BytesIO()
    pdfrw.PdfWriter().write(temp_output, template_pdf)
    temp_output.seek(0)
    _logger.info("Fin du remplissage du PDF")

    return temp_output.read()


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("pdf", "PDF")], ondelete={"pdf": "cascade"}
    )
    report_pdf_template = fields.Binary(string="Report PDF Template")
    report_pdf_template_name = fields.Char(string="Report PDF Template Name")

    @api.constrains("report_type")
    def _check_report_type(self):
        for rec in self:
            if (rec.report_type == "pdf"
                    and not rec.report_pdf_template
                    and not rec.report_pdf_template_name.endswith(".pdf")
            ):
                raise ValidationError(_("Please upload a PDF template."))

    def _spelled_out(self, amount):
        """Convertit un montant numérique en toutes lettres"""
        # Implémentation basique - à adapter selon vos besoins
        try:
            from num2words import num2words
            lang = self._context.get("lang", "en_US")
            if lang.startswith("fr"):
                return num2words(float(amount), lang='fr')
            elif lang.startswith("id"):
                return num2words(float(amount), lang='id')
            else:
                return num2words(float(amount), lang='en')
        except ImportError:
            # Fallback si num2words n'est pas disponible
            return str(amount)
        except (ValueError, TypeError):
            return str(amount)

    def _parse_html(self, html_content):
        """Parse et nettoie le contenu HTML"""
        if not html_content:
            return ""
        # Implémentation basique - à adapter selon vos besoins
        from odoo.tools import html2plaintext
        return html2plaintext(html_content)

    def _formatdate(self, date, format_str=None):
        """Formate une date selon le format spécifié"""
        if not date:
            return ""
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    date = datetime.strptime(date, "%Y-%m-%d")
                except ValueError:
                    return date

        if format_str:
            return date.strftime(format_str)
        else:
            # Format par défaut selon la langue
            lang = self._context.get("lang", "en_US")
            if lang.startswith("fr"):
                return date.strftime("%d/%m/%Y")
            elif lang.startswith("id"):
                return date.strftime("%d-%m-%Y")
            else:
                return date.strftime("%m/%d/%Y")

    def _convert_currency(self, amount, from_currency, to_currency, date=None):
        """Convertit un montant d'une devise à une autre"""
        if not date:
            date = fields.Date.today()

        # Utilise le service de conversion de devises d'Odoo
        try:
            return from_currency._convert(
                amount, to_currency, self.env.company, date
            )
        except Exception as e:
            _logger.warning(f"Erreur de conversion de devise: {e}")
            return amount

    def _render_pdf(self, report_ref, docids, data):
        # Récupération du rapport
        if isinstance(report_ref, str):
            report = self.env.ref(report_ref, raise_if_not_found=False)
            if not report:
                # Recherche par nom de rapport
                report = self.env['ir.actions.report'].search([
                    ('report_name', '=', report_ref)
                ], limit=1)
        else:
            report = report_ref

        if not report:
            raise ValueError(f"Report '{report_ref}' not found.")

        template = report.report_pdf_template

        if not template:
            raise ValueError("No PDF template found.")

        template_pdf = pdfrw.PdfReader(BytesIO(base64.b64decode(template)))
        doc_obj = self.env[report.model].browse(docids)

        context = {
            "spelled_out": self._spelled_out,
            "parsehtml": self._parse_html,
            "formatdate": self._formatdate,
            "company": self.env.company,
            "lang": self._context.get("lang", "en_US"),
            "sysdate": fields.Datetime.now(),
            "convert_currency": self._convert_currency,
        }

        return _fill_pdf(template_pdf, doc_obj, data, context)

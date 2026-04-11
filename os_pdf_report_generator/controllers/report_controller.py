import json
import base64
import pdfrw
from urllib.parse import parse_qs
from odoo.http import (
    content_disposition,
    request,
    route,
    serialize_exception as _serialize_exception,
)
from odoo.tools import html_escape
from odoo.tools.safe_eval import safe_eval, time
from odoo.addons.web.controllers.report import ReportController
from io import BytesIO
import logging

_logger = logging.getLogger(__name__)


def _extract_pdf_fields(template_pdf):
    fields = set()
    for page in template_pdf.pages:
        annotations = page.get('/Annots')
        if annotations:
            for annotation in annotations:
                key = annotation.get('/T')
                if key:
                    field_name = key[1:-1]
                    fields.add(field_name)
    return fields


def _fetch_data(fields, doc_obj):
    """
    Récupère les données pour remplir le PDF.
    Gère les recordsets multiples en créant un dictionnaire des champs communs.
    """
    data = {}

    if not doc_obj:
        return data

    if len(doc_obj) == 1:
        return _fetch_single_record_data(fields, doc_obj)

    return _fetch_multiple_records_data(fields, doc_obj)


def _fetch_single_record_data(fields, doc_obj):
    """Récupère les données pour un seul enregistrement"""
    data = {}
    record = doc_obj[0] if doc_obj else None

    if not record:
        return data

    for field in fields:
        try:
            parts = field.split('.')
            value = record

            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                    if hasattr(value, 'ensure_one') and len(parts) > 1:
                        if len(value) == 1:
                            value = value[0]
                        elif len(value) > 1:
                            value = value[0] if value else None
                        else:
                            value = None
                            break
                else:
                    value = None
                    break

            if value is not None:
                if hasattr(value, 'name'):  # Many2one
                    data[field] = value.name
                elif hasattr(value, 'mapped') and hasattr(value, '__iter__'):  # One2many/Many2many
                    try:
                        data[field] = ', '.join(value.mapped('name'))
                    except Exception:
                        data[field] = str(value)
                else:
                    data[field] = str(value)
        except Exception as e:
            _logger.warning(f"Erreur lors de la récupération du champ {field}: {e}")
            data[field] = ""

    return data


def _fetch_multiple_records_data(fields, doc_objs):
    """
    Récupère les données pour plusieurs enregistrements.
    Retourne les données du premier enregistrement ou des valeurs communes.
    """
    data = {}

    if not doc_objs:
        return data

    first_record = doc_objs[0]

    for field in fields:
        try:
            parts = field.split('.')
            value = first_record

            for part in parts:
                if hasattr(value, part):
                    value = getattr(value, part)
                else:
                    value = None
                    break

            if value is not None:
                if hasattr(value, 'name'):  # Many2one
                    data[field] = value.name
                elif hasattr(value, 'mapped') and hasattr(value, '__iter__'):  # One2many/Many2many
                    try:
                        data[field] = ', '.join(value.mapped('name'))
                    except Exception:
                        data[field] = str(value)
                else:
                    data[field] = str(value)
            else:
                data[field] = ""

        except Exception as e:
            _logger.warning(f"Erreur lors de la récupération du champ {field} pour plusieurs enregistrements: {e}")
            data[field] = ""

    data['_record_count'] = len(doc_objs)
    data['_record_ids'] = ','.join(map(str, doc_objs.ids))

    return data


def _get_filename_by_report_type(report, name):
    filename = "%s.%s" % (name, "pdf")
    return filename


class PdfReportController(ReportController):

    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        """
        CORRECTIF BUG : on intercepte uniquement si le rapport trouvé est
        bien de type "pdf" (notre type custom). Si le rapport n'existe pas
        ou n'est pas de type "pdf", on délègue au comportement standard Odoo
        (QWeb, etc.) pour éviter le crash lorsqu'aucun template n'a été créé.
        """
        if converter == "pdf":
            # Chercher le rapport SANS lever d'exception si absent
            report = self._get_report_from_name_safe(reportname)

            # Si le rapport existe ET est de notre type custom "pdf", on le traite
            if report and report.report_type == "pdf":
                _logger.info("Début de report_routes pour le rapport PDF custom")
                _logger.info(f"Nom du rapport : {reportname}")
                _logger.info(f"DocIDs : {docids}")

                context = dict(request.env.context)

                if docids:
                    docids = [int(i) for i in docids.split(",")]
                if data.get("options"):
                    options = json.loads(data.pop("options"))
                    data.update(options)
                if data.get("context"):
                    context_data = json.loads(data["context"])
                    data["context"] = context_data
                    context.update(context_data)

                # Vérifier et consommer un crédit d'impression
                company = request.env.company
                remaining, warning_message = company._check_and_consume_print_credit()

                template = report.report_pdf_template
                if not template:
                    from odoo.exceptions import UserError
                    raise UserError("No PDF template found for this report.")

                template_pdf = pdfrw.PdfReader(BytesIO(base64.b64decode(template)))
                fields = _extract_pdf_fields(template_pdf)
                _logger.info(f"Champs trouvés dans le PDF : {fields}")

                doc_obj = request.env[report.model].browse(docids)
                _logger.info(f"Nombre d'enregistrements à traiter : {len(doc_obj)}")

                pdf_data = _fetch_data(fields, doc_obj)
                _logger.info(f"Données récupérées : {pdf_data}")

                pdf_files = report.with_context(**context)._render_pdf(
                    reportname, docids, data=pdf_data
                )

                httpheaders = [('Content-Type', 'application/pdf')]

                # Si un avertissement de crédit est à afficher, on le logue
                # (il sera affiché via report_download qui peut gérer les notifications)
                if warning_message:
                    _logger.warning(
                        "Credit warning for company %s: %s", company.name, warning_message
                    )
                    # Stocker le warning en session pour l'afficher côté client
                    request.session['pdf_credit_warning'] = warning_message

                _logger.info("Fin de report_routes pour le rapport PDF custom")
                return request.make_response(pdf_files, headers=httpheaders)

            # Pas notre type, ou rapport standard QWeb : on passe au parent
            # Cela corrige le bug lors d'une impression standard sans template custom

        return super().report_routes(reportname, docids, converter, **data)

    def _get_report_from_name_safe(self, reportname):
        """
        Récupère un rapport par son nom SANS lever d'exception si introuvable.
        Retourne None si le rapport n'existe pas.
        """
        try:
            report = request.env.ref(reportname, raise_if_not_found=False)
            if report:
                return report
            report = request.env['ir.actions.report'].search([
                ('report_name', '=', reportname)
            ], limit=1)
            return report or None
        except Exception:
            return None

    def _get_report_from_name(self, reportname):
        """Récupère un rapport par son nom (lève une exception si introuvable)."""
        report = self._get_report_from_name_safe(reportname)
        if not report:
            raise ValueError(f"Report '{reportname}' not found.")
        return report

    @route()
    def report_download(self, data, context=None, token=None):
        requestcontent = json.loads(data)
        url, report_type = requestcontent[0], requestcontent[1]
        try:
            if report_type == "pdf":
                reportname = url.split("/report/pdf/")[1].split("?")[0]
                docids = None
                if "/" in reportname:
                    reportname, docids = reportname.split("/")
                if docids:
                    response = self.report_routes(
                        reportname, docids=docids, converter="pdf", context=context
                    )
                else:
                    data = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(url.split("?")[1]).items()}

                    if "context" in data:
                        context, data_context = json.loads(context or "{}"), json.loads(
                            data.pop("context")
                        )
                        context = json.dumps({**context, **data_context})
                    response = self.report_routes(
                        reportname, docids=docids, converter="pdf", context=context, **data
                    )

                # Si la réponse n'est pas un PDF custom (ex: QWeb standard),
                # on laisse le parent gérer le Content-Disposition
                if not hasattr(response, 'headers'):
                    return response

                report = self._get_report_from_name_safe(reportname)
                if not report or report.report_type != "pdf":
                    # Rapport standard : laisser le parent gérer le téléchargement
                    return super().report_download(
                        json.dumps(requestcontent), context=context, token=token
                    )

                filename = _get_filename_by_report_type(report, report.name)

                if docids:
                    ids = [int(x) for x in docids.split(",")]
                    obj = request.env[report.model].browse(ids)
                    if report.print_report_name and not len(obj) > 1:
                        try:
                            single_obj = obj[0] if len(obj) == 1 else obj
                            report_name = safe_eval(
                                report.print_report_name, {"object": single_obj, "time": time}
                            )
                            filename = _get_filename_by_report_type(report, report_name)
                        except Exception as e:
                            _logger.warning(f"Erreur lors de l'évaluation du nom de rapport : {e}")
                            filename = _get_filename_by_report_type(
                                report, f"{report.name}_{len(obj)}_records"
                            )

                if not response.headers.get("Content-Disposition"):
                    response.headers.add(
                        "Content-Disposition", content_disposition(filename)
                    )

                # Afficher le warning crédit si présent en session
                credit_warning = request.session.pop('pdf_credit_warning', None)
                if credit_warning:
                    # On ajoute le warning dans les headers custom pour que le JS puisse le lire
                    response.headers.add("X-Pdf-Credit-Warning", credit_warning)

                return response
            else:
                return super().report_download(data, context=context, token=token)
        except Exception as e:
            se = _serialize_exception(e)
            error = {"code": 200, "message": "Odoo Server Error", "data": se}
            return request.make_response(html_escape(json.dumps(error)))

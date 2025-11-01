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

    # Si c'est un recordset vide, retourner un dictionnaire vide
    if not doc_obj:
        return data

    # Si c'est un seul enregistrement
    if len(doc_obj) == 1:
        return _fetch_single_record_data(fields, doc_obj)

    # Si ce sont plusieurs enregistrements, traiter différemment
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
                    # Si c'est un recordset et qu'on a encore des parties à traiter
                    if hasattr(value, 'ensure_one') and len(parts) > 1:
                        if len(value) == 1:
                            value = value[0]
                        elif len(value) > 1:
                            # Pour les relations multiples, prendre le premier
                            value = value[0] if value else None
                        else:
                            value = None
                            break
                else:
                    value = None
                    break

            if value is not None:
                # Traitement spécial selon le type de valeur
                if hasattr(value, 'name'):  # Many2one
                    data[field] = value.name
                elif hasattr(value, 'mapped') and hasattr(value, '__iter__'):  # One2many/Many2many
                    try:
                        data[field] = ', '.join(value.mapped('name'))
                    except:
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

    # Utiliser le premier enregistrement comme base
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
                # Traitement spécial selon le type de valeur
                if hasattr(value, 'name'):  # Many2one
                    data[field] = value.name
                elif hasattr(value, 'mapped') and hasattr(value, '__iter__'):  # One2many/Many2many
                    try:
                        data[field] = ', '.join(value.mapped('name'))
                    except:
                        data[field] = str(value)
                else:
                    data[field] = str(value)
            else:
                data[field] = ""

        except Exception as e:
            _logger.warning(f"Erreur lors de la récupération du champ {field} pour plusieurs enregistrements: {e}")
            data[field] = ""

    # Ajouter des informations sur le nombre d'enregistrements
    data['_record_count'] = len(doc_objs)
    data['_record_ids'] = ','.join(map(str, doc_objs.ids))

    return data


def _get_filename_by_report_type(report, name):
    filename = "%s.%s" % (name, "pdf")
    return filename


class PdfReportController(ReportController):
    @route()
    def report_routes(self, reportname, docids=None, converter=None, **data):
        if converter == "pdf":
            _logger.info("Début de report_routes pour le rapport PDF")
            _logger.info(f"Nom du rapport : {reportname}")
            _logger.info(f"DocIDs : {docids}")
            _logger.info(f"Données initiales : {data}")

            # Utilisation de la méthode correcte pour récupérer le rapport
            report = self._get_report_from_name(reportname)
            context = dict(request.env.context)

            if docids:
                docids = [int(i) for i in docids.split(",")]
                _logger.info(f"DocIDs après conversion : {docids}")
            if data.get("options"):
                options = json.loads(data.pop("options"))
                data.update(options)
                _logger.info(f"Données après ajout des options : {data}")
            if data.get("context"):
                context_data = json.loads(data["context"])
                data["context"] = context_data
                context.update(context_data)
                _logger.info(f"Contexte après ajout des données de contexte : {context}")

            # Inspecter le formulaire PDF pour récupérer les champs utilisés
            template = report.report_pdf_template
            if not template:
                raise ValueError("No PDF template found.")
            template_pdf = pdfrw.PdfReader(BytesIO(base64.b64decode(template)))
            fields = _extract_pdf_fields(template_pdf)
            _logger.info(f"Champs trouvés dans le PDF : {fields}")

            # Récupérer les données nécessaires
            doc_obj = request.env[report.model].browse(docids)
            _logger.info(f"Nombre d'enregistrements à traiter : {len(doc_obj)}")

            data = _fetch_data(fields, doc_obj)
            _logger.info(f"Données récupérées : {data}")

            pdf_files = report.with_context(**context)._render_pdf(reportname, docids, data=data)

            httpheaders = [
                ('Content-Type', 'application/pdf'),
            ]
            _logger.info("Fin de report_routes pour le rapport PDF")
            return request.make_response(pdf_files, headers=httpheaders)

        return super().report_routes(reportname, docids, converter, **data)

    def _get_report_from_name(self, reportname):
        """Récupère un rapport par son nom"""
        # Essayer d'abord avec une référence externe
        report = request.env.ref(reportname, raise_if_not_found=False)
        if report:
            return report

        # Sinon rechercher par report_name
        report = request.env['ir.actions.report'].search([
            ('report_name', '=', reportname)
        ], limit=1)

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
                    # data = dict(
                    #     url_decode(url.split("?")[1]).items()
                    # )
                    data = {k: v[0] if len(v) == 1 else v for k, v in parse_qs(url.split("?")[1]).items()}

                    if "context" in data:
                        context, data_context = json.loads(context or "{}"), json.loads(
                            data.pop("context")
                        )
                        context = json.dumps({**context, **data_context})
                    response = self.report_routes(
                        reportname, docids=docids, converter="pdf", context=context, **data
                    )

                report = self._get_report_from_name(reportname)

                filename = _get_filename_by_report_type(report, report.name)

                if docids:
                    ids = [int(x) for x in docids.split(",")]
                    obj = request.env[report.model].browse(ids)
                    if report.print_report_name and not len(obj) > 1:
                        try:
                            # S'assurer qu'on a un seul enregistrement pour safe_eval
                            single_obj = obj[0] if len(obj) == 1 else obj
                            report_name = safe_eval(
                                report.print_report_name, {"object": single_obj, "time": time}
                            )
                            filename = _get_filename_by_report_type(report, report_name)
                        except Exception as e:
                            _logger.warning(f"Erreur lors de l'évaluation du nom de rapport : {e}")
                            # Utiliser un nom par défaut
                            filename = _get_filename_by_report_type(report, f"{report.name}_{len(obj)}_records")

                if not response.headers.get("Content-Disposition"):
                    response.headers.add(
                        "Content-Disposition", content_disposition(filename)
                    )
                return response
            else:
                return super().report_download(data, context=context, token=token)
        except Exception as e:
            se = _serialize_exception(e)
            error = {"code": 200, "message": "Odoo Server Error", "data": se}
            return request.make_response(html_escape(json.dumps(error)))

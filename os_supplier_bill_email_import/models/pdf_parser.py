# -*- coding: utf-8 -*-
"""
Utilitaires d'extraction de texte depuis un PDF.

Priorité des moteurs :
  1. pdfminer.six  (le plus précis pour les PDFs comptables)
  2. pypdf         (fallback léger, souvent présent dans Odoo)
  3. PyPDF2        (ancien nom, encore présent sur certaines installs)
  4. Erreur explicite si aucun moteur n'est disponible

Usage :
    from .pdf_parser import extract_pdf_text, PDF_AVAILABLE
    text = extract_pdf_text(pdf_bytes)
"""

import logging

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Détection des moteurs disponibles au démarrage du module
# ──────────────────────────────────────────────────────────────────────────────

_PDFMINER_OK = False
_PYPDF_OK = False
_PYPDF2_OK = False

try:
    from pdfminer.high_level import extract_text_to_fp  # noqa: F401
    from pdfminer.layout import LAParams               # noqa: F401
    _PDFMINER_OK = True
except ImportError:
    pass

if not _PDFMINER_OK:
    try:
        from pypdf import PdfReader as _PypdfReader    # noqa: F401
        _PYPDF_OK = True
    except ImportError:
        pass

if not _PDFMINER_OK and not _PYPDF_OK:
    try:
        from PyPDF2 import PdfReader as _PyPDF2Reader  # noqa: F401
        _PYPDF2_OK = True
    except ImportError:
        pass

PDF_AVAILABLE = _PDFMINER_OK or _PYPDF_OK or _PYPDF2_OK

if not PDF_AVAILABLE:
    _logger.warning(
        "supplier_bill_email_import: aucune bibliothèque PDF disponible "
        "(pdfminer.six, pypdf ou PyPDF2). "
        "Installez : pip install pdfminer.six"
    )
else:
    engine = (
        "pdfminer.six" if _PDFMINER_OK
        else ("pypdf" if _PYPDF_OK else "PyPDF2")
    )
    _logger.info(
        "supplier_bill_email_import: moteur PDF sélectionné → %s", engine
    )


# ──────────────────────────────────────────────────────────────────────────────
# Fonction principale
# ──────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes):
    """
    Extrait le texte brut d'un PDF fourni sous forme de bytes.

    Returns:
        str  — texte extrait (peut être vide si le PDF est une image scannée)
    Raises:
        RuntimeError  — si aucun moteur PDF n'est installé
        Exception     — en cas d'erreur de lecture propre au PDF
    """
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "Impossible d'extraire le texte du PDF : aucune bibliothèque "
            "disponible. Installez pdfminer.six : pip install pdfminer.six"
        )

    if _PDFMINER_OK:
        return _extract_pdfminer(pdf_bytes)
    if _PYPDF_OK:
        return _extract_pypdf(pdf_bytes)
    return _extract_pypdf2(pdf_bytes)


# ──────────────────────────────────────────────────────────────────────────────
# Moteurs internes
# ──────────────────────────────────────────────────────────────────────────────

def _extract_pdfminer(pdf_bytes):
    import io
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams

    input_buf = io.BytesIO(pdf_bytes)
    output_buf = io.StringIO()
    try:
        extract_text_to_fp(
            input_buf, output_buf,
            laparams=LAParams(
                line_overlap=0.5,
                char_margin=2.0,
                line_margin=0.5,
                word_margin=0.1,
            ),
            output_type='text',
            codec=None,
        )
        text = output_buf.getvalue()
    except Exception as exc:
        _logger.error("pdfminer: erreur extraction — %s", exc)
        raise
    finally:
        input_buf.close()
        output_buf.close()

    return _normalise(text)


def _extract_pypdf(pdf_bytes):
    import io
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or '')
        except Exception as exc:
            _logger.warning("pypdf: erreur page — %s", exc)
    return _normalise('\n'.join(parts))


def _extract_pypdf2(pdf_bytes):
    import io
    from PyPDF2 import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or '')
        except Exception as exc:
            _logger.warning("PyPDF2: erreur page — %s", exc)
    return _normalise('\n'.join(parts))


# ──────────────────────────────────────────────────────────────────────────────
# Normalisation commune
# ──────────────────────────────────────────────────────────────────────────────

def _normalise(text):
    """
    Remplace les espaces insécables et normalise les espaces répétés
    pour faciliter les regex de parsing.
    """
    if not text:
        return ''
    # Espaces insécables → espace ordinaire
    text = text.replace('\u00a0', ' ').replace('\u202f', ' ').replace('\xa0', ' ')
    # Supprimer les retours chariot Windows
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text

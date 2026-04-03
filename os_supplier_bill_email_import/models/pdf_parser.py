# -*- coding: utf-8 -*-
"""
Utilitaires d'extraction de texte depuis un PDF ou une image.

Priorité des moteurs pour les PDFs texte :
  1. pdfminer.six  (le plus précis pour les PDFs comptables)
  2. pypdf         (fallback léger, souvent présent dans Odoo)
  3. PyPDF2        (ancien nom, encore présent sur certaines installs)

OCR (fallback automatique si le PDF est un scan ou si la pièce jointe est une image) :
  4. pytesseract + pdf2image  (PDF scan → images → OCR)
  5. pytesseract + Pillow     (image directe JPG/PNG → OCR)

Installation :
    pip install pdfminer.six          # extraction texte PDF (recommandé)
    pip install pdf2image pytesseract  # OCR pour scans et images
    apt install tesseract-ocr tesseract-ocr-fra  # moteur OCR système

Usage :
    from .pdf_parser import extract_pdf_text, extract_image_text, PDF_AVAILABLE, OCR_AVAILABLE
    text = extract_pdf_text(pdf_bytes)   # PDF texte ou scan
    text = extract_image_text(img_bytes, mimetype='image/jpeg')  # image directe
"""

import logging
import io

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Détection des moteurs texte PDF
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

# ──────────────────────────────────────────────────────────────────────────────
# Détection des moteurs OCR
# ──────────────────────────────────────────────────────────────────────────────

_PYTESSERACT_OK = False
_PDF2IMAGE_OK = False
_PILLOW_OK = False

try:
    import pytesseract  # noqa: F401
    _PYTESSERACT_OK = True
except ImportError:
    pass

if _PYTESSERACT_OK:
    try:
        from pdf2image import convert_from_bytes  # noqa: F401
        _PDF2IMAGE_OK = True
    except ImportError:
        pass

    try:
        from PIL import Image  # noqa: F401
        _PILLOW_OK = True
    except ImportError:
        pass

OCR_AVAILABLE = _PYTESSERACT_OK and (_PDF2IMAGE_OK or _PILLOW_OK)

# ──────────────────────────────────────────────────────────────────────────────
# Seuil de détection d'un scan (texte trop court = probablement un scan)
# ──────────────────────────────────────────────────────────────────────────────

_MIN_TEXT_LENGTH = 50  # caractères minimum pour considérer l'extraction réussie

# ──────────────────────────────────────────────────────────────────────────────
# Logs de démarrage
# ──────────────────────────────────────────────────────────────────────────────

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
        "supplier_bill_email_import: moteur PDF texte → %s", engine
    )

if OCR_AVAILABLE:
    ocr_pdf_engine = "pdf2image" if _PDF2IMAGE_OK else "(pas de pdf2image)"
    _logger.info(
        "supplier_bill_email_import: OCR disponible → pytesseract + %s + Pillow=%s",
        ocr_pdf_engine, _PILLOW_OK,
    )
else:
    if not _PYTESSERACT_OK:
        _logger.info(
            "supplier_bill_email_import: OCR non disponible (pytesseract absent). "
            "Pour activer l'OCR sur les scans/images : "
            "pip install pdf2image pytesseract && apt install tesseract-ocr"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Fonction principale PDF
# ──────────────────────────────────────────────────────────────────────────────

def extract_pdf_text(pdf_bytes):
    """
    Extrait le texte d'un PDF, avec fallback OCR si le PDF est un scan.

    Stratégie :
      1. Extraction texte normale (pdfminer/pypdf/PyPDF2).
      2. Si le résultat est trop court (< _MIN_TEXT_LENGTH caractères),
         le PDF est probablement un scan — on tente l'OCR via pytesseract.

    Args:
        pdf_bytes (bytes) : contenu brut du fichier PDF

    Returns:
        str  — texte extrait (peut être vide si scan et OCR absent/échoué)

    Raises:
        RuntimeError  — si aucun moteur PDF n'est installé
        Exception     — en cas d'erreur de lecture
    """
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "Impossible d'extraire le texte du PDF : aucune bibliothèque "
            "disponible. Installez pdfminer.six : pip install pdfminer.six"
        )

    # ── Étape 1 : extraction texte normale ───────────────────────────────────
    if _PDFMINER_OK:
        text = _extract_pdfminer(pdf_bytes)
    elif _PYPDF_OK:
        text = _extract_pypdf(pdf_bytes)
    else:
        text = _extract_pypdf2(pdf_bytes)

    if len(text.strip()) >= _MIN_TEXT_LENGTH:
        _logger.debug(
            "extract_pdf_text : texte extrait (%d car.) — pas d'OCR nécessaire.",
            len(text.strip()),
        )
        return text

    # ── Étape 2 : fallback OCR si texte trop court ────────────────────────────
    if not OCR_AVAILABLE:
        _logger.warning(
            "extract_pdf_text : texte extrait trop court (%d car.) — "
            "PDF probablement scanné, mais OCR non disponible. "
            "Installez : pip install pdf2image pytesseract "
            "&& apt install tesseract-ocr",
            len(text.strip()),
        )
        return text

    if not _PDF2IMAGE_OK:
        _logger.warning(
            "extract_pdf_text : texte court (%d car.) et pdf2image absent — "
            "impossible de convertir le scan en images pour l'OCR. "
            "Installez : pip install pdf2image && apt install poppler-utils",
            len(text.strip()),
        )
        return text

    _logger.info(
        "extract_pdf_text : texte court (%d car.) — OCR du scan en cours…",
        len(text.strip()),
    )
    ocr_text = _ocr_pdf(pdf_bytes)
    if len(ocr_text.strip()) > len(text.strip()):
        _logger.info(
            "extract_pdf_text : OCR réussi (%d car. extraits).",
            len(ocr_text.strip()),
        )
        return ocr_text

    _logger.warning(
        "extract_pdf_text : OCR produit moins de texte (%d car.) que "
        "l'extraction directe (%d car.) — résultat direct conservé.",
        len(ocr_text.strip()), len(text.strip()),
    )
    return text


# ──────────────────────────────────────────────────────────────────────────────
# Fonction image directe (JPEG, PNG, TIFF, BMP…)
# ──────────────────────────────────────────────────────────────────────────────

def extract_image_text(image_bytes, mimetype=''):
    """
    Extrait le texte d'une pièce jointe image (JPEG, PNG, TIFF, BMP, WEBP)
    via OCR pytesseract.

    Args:
        image_bytes (bytes) : contenu brut de l'image
        mimetype    (str)   : type MIME (ex: 'image/jpeg'), optionnel

    Returns:
        str  — texte extrait par OCR (peut être vide)

    Raises:
        RuntimeError  — si pytesseract/Pillow ne sont pas disponibles
    """
    if not _PYTESSERACT_OK:
        raise RuntimeError(
            "OCR non disponible : pytesseract absent. "
            "Installez : pip install pytesseract "
            "&& apt install tesseract-ocr"
        )
    if not _PILLOW_OK:
        raise RuntimeError(
            "OCR non disponible : Pillow absent. "
            "Installez : pip install Pillow"
        )

    _logger.info(
        "extract_image_text : OCR image (%s, %d octets)…",
        mimetype or '?', len(image_bytes),
    )

    try:
        from PIL import Image
        import pytesseract

        image = Image.open(io.BytesIO(image_bytes))
        # Conversion en RGB si nécessaire (pour CMYK, RGBA, etc.)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        text = pytesseract.image_to_string(
            image,
            lang=_get_tesseract_lang(),
            config='--psm 6',  # Assume un bloc de texte uniforme
        )
        text = _normalise(text)
        _logger.info(
            "extract_image_text : OCR réussi (%d car.).", len(text.strip())
        )
        return text

    except Exception as exc:
        _logger.error("extract_image_text : erreur OCR — %s", exc)
        raise


# ──────────────────────────────────────────────────────────────────────────────
# Moteurs texte internes
# ──────────────────────────────────────────────────────────────────────────────

def _extract_pdfminer(pdf_bytes):
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
# Moteur OCR interne
# ──────────────────────────────────────────────────────────────────────────────

def _ocr_pdf(pdf_bytes):
    """
    Convertit chaque page du PDF en image puis applique l'OCR pytesseract.

    Nécessite : pdf2image (pip install pdf2image) et poppler (apt install poppler-utils).
    """
    from pdf2image import convert_from_bytes
    import pytesseract

    try:
        pages = convert_from_bytes(
            pdf_bytes,
            dpi=300,          # résolution suffisante pour un bon OCR
            fmt='jpeg',
            thread_count=2,
        )
    except Exception as exc:
        _logger.error("_ocr_pdf: conversion PDF→images échouée — %s", exc)
        return ''

    parts = []
    lang = _get_tesseract_lang()
    for i, page_image in enumerate(pages, 1):
        try:
            page_text = pytesseract.image_to_string(
                page_image,
                lang=lang,
                config='--psm 6',
            )
            parts.append(page_text)
        except Exception as exc:
            _logger.warning("_ocr_pdf: erreur OCR page %d — %s", i, exc)

    return _normalise('\n'.join(parts))


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────────────

def _get_tesseract_lang():
    """
    Retourne la chaîne de langues Tesseract à utiliser.
    Tente fra+eng si le pack français est installé, sinon eng seul.
    """
    try:
        import pytesseract
        langs = pytesseract.get_languages()
        if 'fra' in langs:
            return 'fra+eng'
        return 'eng'
    except Exception:
        return 'fra+eng'  # tentative par défaut


def _normalise(text):
    """
    Remplace les espaces insécables et normalise les espaces répétés
    pour faciliter les regex de parsing.
    """
    if not text:
        return ''
    text = text.replace('\u00a0', ' ').replace('\u202f', ' ').replace('\xa0', ' ')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text

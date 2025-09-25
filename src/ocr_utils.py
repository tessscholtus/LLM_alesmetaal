# src/ocr_utils.py
# Algemene OCR: pdfplumber -> (fallback) Tesseract met hoge DPI en preprocess
from typing import List
import os

import pdfplumber
import pdf2image
import pytesseract
from PIL import Image, ImageOps, ImageEnhance
from loguru import logger

# Logging naar bestand (optioneel)
logger.add("file.log", rotation="500 MB", level="INFO")

def _extract_text_with_pdfplumber(pdf_path: str) -> str:
    """
    Extract tekst uit tekst-gebaseerde PDF's met pdfplumber.
    (Faalt doorgaans bij gescande PDF's zonder tekstlaag.)
    """
    full_text_parts: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    full_text_parts.append(text)
                else:
                    logger.debug(
                        f"Geen tekst gevonden met pdfplumber op pagina "
                        f"{page.page_number} van {pdf_path}"
                    )
        return "\n".join(full_text_parts)
    except Exception as e:
        logger.error(f"Fout bij pdfplumber extractie van {pdf_path}: {e}")
        return ""

def _preprocess_variants(img: Image.Image) -> List[Image.Image]:
    """
    Maak meerdere beeldvarianten om OCR te verbeteren:
    - Grijs + autocontrast
    - Extra contrast
    - Binarisaties met verschillende drempels
    """
    variants: List[Image.Image] = []
    g = img.convert("L")
    g = ImageOps.autocontrast(g)
    variants.append(g)

    g2 = ImageEnhance.Contrast(g).enhance(1.6)
    variants.append(g2)

    bw_high = g2.point(lambda p: 255 if p > 180 else 0)
    variants.append(bw_high)

    bw_mid = g2.point(lambda p: 255 if p > 165 else 0)
    variants.append(bw_mid)

    return variants

def _ocr_image(img: Image.Image, lang: str = "nld+eng") -> str:
    """
    Voer Tesseract uit met meerdere PSM-modi op meerdere varianten.
    """
    texts: List[str] = []
    cfgs = [
        "--oem 3 --psm 6",   # 'Assume a single uniform block of text'
        "--oem 3 --psm 4",   # 'Single column'
        "--oem 3 --psm 11",  # 'Sparse text'
    ]
    for v in _preprocess_variants(img):
        for cfg in cfgs:
            try:
                t = pytesseract.image_to_string(v, lang=lang, config=cfg)
                if t and t.strip():
                    texts.append(t)
            except Exception as e:
                logger.debug(f"Tesseract error ({cfg}): {e}")
    return "\n".join(texts)

def _extract_text_with_tesseract_ocr(
    pdf_path: str,
    lang: str = "nld+eng",
    dpi: int = 350,
) -> str:
    """
    Converteer elke PDF-pagina naar een afbeelding (hoge DPI) en voer OCR uit
    met diverse preprocess-varianten en PSM-modi.
    """
    try:
        images: List[Image.Image] = pdf2image.convert_from_path(pdf_path, dpi=dpi)
    except Exception as e:
        logger.error(f"pdf2image convert_from_path failed voor {pdf_path}: {e}")
        return ""

    parts: List[str] = []
    for i, image in enumerate(images, start=1):
        page_txt = _ocr_image(image, lang=lang)
        if not page_txt.strip():
            logger.debug(f"Tesseract gaf geen tekst op pagina {i} van {pdf_path}")
        parts.append(page_txt)
    return "\n".join(parts)

def extract_text_from_pdf_robust(pdf_path: str) -> str:
    """
    Robuuste wrapper:
      1) probeer pdfplumber (snel, tekstlaag)
      2) zo niet: fallback naar Tesseract OCR (gescand)
    """
    if not os.path.exists(pdf_path):
        logger.error(f"PDF-bestand niet gevonden: {pdf_path}")
        return ""

    logger.info(f"Start robuuste tekstextractie voor {pdf_path}...")

    # 1) Probeer pdfplumber
    text_plumber = _extract_text_with_pdfplumber(pdf_path)
    if text_plumber and text_plumber.strip():
        logger.info(f"Tekst succesvol geëxtraheerd met pdfplumber uit {pdf_path}.")
        return text_plumber

    logger.warning(
        f"Pdfplumber vond geen significante tekst in {pdf_path}. "
        "Valt terug op Tesseract OCR."
    )

    # 2) Tesseract fallback
    text_ocr = _extract_text_with_tesseract_ocr(pdf_path)
    if text_ocr and text_ocr.strip():
        logger.info(f"Tekst succesvol geëxtraheerd met Tesseract OCR uit {pdf_path}.")
        return text_ocr

    logger.error(
        f"Geen tekst geëxtraheerd uit {pdf_path} via pdfplumber of Tesseract OCR."
    )
    return ""

if __name__ == "__main__":
    # Handige CLI test:
    # python src/ocr_utils.py /pad/naar/bestand.pdf
    import sys, textwrap
    test_pdf = sys.argv[1] if len(sys.argv) > 1 else ""
    if not test_pdf:
        print("Gebruik: python src/ocr_utils.py /pad/naar/bestand.pdf")
        sys.exit(1)
    txt = extract_text_from_pdf_robust(test_pdf)
    print(f"\n--- OCR lengte: {len(txt)} ---")
    print(textwrap.shorten(txt.replace("\n", " "), width=1200, placeholder=" ..."))

# main.py — OCR -> Gemini -> JSON
import sys, json
from pathlib import Path
from loguru import logger

from config import settings
from src.ocr_utils import extract_text_from_pdf_robust
from src.llm_extractor import extract_fields_with_llm

# Log naar outputs/process.log
logger.add(settings.OUTPUT_DIR / "process.log", rotation="500 MB", level=settings.LOG_LEVEL)

def process_single_pdf(pdf_path: Path):
    logger.info(f"Start verwerking van PDF: {pdf_path}")
    text = extract_text_from_pdf_robust(str(pdf_path))
    if not text:
        logger.error("Geen tekst uit OCR.")
        return None
    logger.info(f"OCR gelukt (len={len(text)}). LLM extractie starten…")
    data = extract_fields_with_llm(text)
    logger.info(f"LLM klaar: {data}")
    return data

if __name__ == "__main__":
    # Pas dit pad aan indien je een andere PDF wilt testen
    test_pdf = Path("/Users/tessscholtus/Elten_data/MD-22-07091_2/MD-22-07091_2.pdf")
    if not test_pdf.exists():
        logger.error(f"Bestand niet gevonden: {test_pdf}")
        sys.exit(1)

    print(f"\n--- LLM extractie voor: {test_pdf} ---\n")
    result = process_single_pdf(test_pdf)
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nLog: {settings.OUTPUT_DIR}/process.log")
    else:
        print("Verwerking mislukt. Check logs.")

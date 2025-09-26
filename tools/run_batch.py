# tools/run_batch.py

import csv
import sys
import json
from pathlib import Path
from loguru import logger

# --- Path Configuration ---
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Import Settings and Modules ---
try:
    from config import settings
    from src.ocr_utils import extract_text_from_pdf_robust
    from src.llm_extractor import extract_fields_with_llm, TARGET_KEYS
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you are running this script from the project's root directory.")
    sys.exit(1)

# --- CSV Header Definition ---
CSV_FIELDS = [
    "PDF_Filename",
    "Drawing_Number",
    "Revision",
    # Surface & standards
    "Surface_Roughness_Standard",
    "Surface_Roughness_Parameter",
    "Surface_Roughness_Value",
    "Surface_Roughness_Unit",
    "Geometrical_Tolerancing_Standard",
    "Geometrical_Tolerancing_Scope",
    "Dimensional_Tolerancing_Standard",
    "Dimensional_Tolerancing_Scope",
    # Booleans & welding
    "Break_Sharp_Edges",
    "Retaining_Ring_Grooves_Sharp",
    "Welding_Notes",
    "Welding_Designation",
    "Weld_Finish",
    "Post_Treatment",
    "Material_Grade",
    # Tolerance tables (3x4 bands)
    "Tol_General_0-20",
    "Tol_General_20-200",
    "Tol_General_200-2000",
    "Tol_General_>2000",
    "Tol_Machining_0-20",
    "Tol_Machining_20-200",
    "Tol_Machining_200-2000",
    "Tol_Machining_>2000",
    "Tol_Welded_0-20",
    "Tol_Welded_20-200",
    "Tol_Welded_200-2000",
    "Tol_Welded_>2000",
    # Free notes at the end
    "Notes",
]

def process_single_pdf(pdf_path: Path):
    logger.info(f"Processing PDF: {pdf_path.name}")
    ocr_text = extract_text_from_pdf_robust(str(pdf_path))
    if not ocr_text or not ocr_text.strip():
        logger.warning(f"No significant OCR text extracted for {pdf_path.name}. Skipping LLM.")
        return None
    logger.debug(f"OCR for {pdf_path.name} successful (text length: {len(ocr_text)}).")

    logger.info(f"Starting LLM extraction for {pdf_path.name}...")
    extracted_data = extract_fields_with_llm(ocr_text)

    if not extracted_data or all(
        v is None or (isinstance(v, (list, str)) and not v)
        for k, v in extracted_data.items() if k in TARGET_KEYS
    ):
        logger.warning(f"LLM extraction returned no relevant data for {pdf_path.name}.")
        return None

    logger.success(f"LLM extraction complete for {pdf_path.name}.")
    return extracted_data

def _bands(d: dict | None, key: str) -> str:
    if not isinstance(d, dict):
        return ""
    b = d.get("bands") or {}
    return str(b.get(key, "") or "")

def prepare_csv_row(pdf_path: Path, extracted_data: dict) -> dict:
    if not extracted_data:
        return {field: "" for field in CSV_FIELDS}

    row = {}
    row["PDF_Filename"] = pdf_path.name

    # Drawing & revision
    row["Drawing_Number"] = extracted_data.get("Drawing_Number", "")
    row["Revision"] = extracted_data.get("Revision", "")

    # Surface roughness
    sr = extracted_data.get("Surface_Roughness") or {}
    row["Surface_Roughness_Standard"] = sr.get("standard", "") if isinstance(sr, dict) else ""
    row["Surface_Roughness_Parameter"] = sr.get("parameter", "") if isinstance(sr, dict) else ""
    row["Surface_Roughness_Value"] = sr.get("value", "") if isinstance(sr, dict) else ""
    row["Surface_Roughness_Unit"] = sr.get("unit", "") if isinstance(sr, dict) else ""

    # Geometrical / dimensional
    gt = extracted_data.get("Geometrical_Tolerancing") or {}
    dt = extracted_data.get("Dimensional_Tolerancing") or {}
    row["Geometrical_Tolerancing_Standard"] = gt.get("standard", "") if isinstance(gt, dict) else ""
    row["Geometrical_Tolerancing_Scope"] = gt.get("scope", "") if isinstance(gt, dict) else ""
    row["Dimensional_Tolerancing_Standard"] = dt.get("standard", "") if isinstance(dt, dict) else ""
    row["Dimensional_Tolerancing_Scope"] = dt.get("scope", "") if isinstance(dt, dict) else ""

    # Booleans & welding
    row["Break_Sharp_Edges"] = str(bool(extracted_data.get("Break_Sharp_Edges", False)))
    row["Retaining_Ring_Grooves_Sharp"] = str(bool(extracted_data.get("Retaining_Ring_Grooves_Sharp", False)))
    welding_notes = extracted_data.get("Welding_Notes", [])
    row["Welding_Notes"] = " | ".join(welding_notes) if isinstance(welding_notes, list) else (welding_notes or "")
    row["Welding_Designation"] = extracted_data.get("Welding_Designation", "") or ""
    row["Weld_Finish"] = extracted_data.get("Weld_Finish", "") or ""
    row["Post_Treatment"] = extracted_data.get("Post_Treatment", "") or ""
    row["Material_Grade"] = extracted_data.get("Material_Grade", "") or ""

    # Tolerance tables
    tg = extracted_data.get("Tolerances_General_Linear")
    tm = extracted_data.get("Tolerances_Machining")
    tw = extracted_data.get("Tolerances_Welded_Sheetmetal")
    for band in ("0-20","20-200","200-2000",">2000"):
        row[f"Tol_General_{band}"]   = _bands(tg, band)
        row[f"Tol_Machining_{band}"] = _bands(tm, band)
        row[f"Tol_Welded_{band}"]    = _bands(tw, band)

    # Notes
    notes = extracted_data.get("Notes", [])
    row["Notes"] = " | ".join(notes) if isinstance(notes, list) else (notes or "")

    final_row = {field: row.get(field, "") for field in CSV_FIELDS}
    return final_row

def process_directory_for_csv(root_path: Path, output_csv_path: Path):
    logger.info(f"Scanning for PDF files in: {root_path}")
    pdf_files = sorted(list(root_path.rglob("*.pdf")))
    if not pdf_files:
        logger.warning(f"No PDF files found under {root_path}.")
        return

    logger.info(f"Found {len(pdf_files)} PDF files to process.")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    processed_count = 0
    failed_count = 0
    with output_csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for pdf_path in pdf_files:
            extracted_data = process_single_pdf(pdf_path)
            if extracted_data:
                csv_row = prepare_csv_row(pdf_path, extracted_data)
                writer.writerow(csv_row)
                processed_count += 1
            else:
                logger.warning(f"Skipping CSV row for {pdf_path.name} due to missing data or extraction failure.")
                failed_count += 1
                empty_row = {field: "" for field in CSV_FIELDS}
                empty_row["PDF_Filename"] = pdf_path.name
                writer.writerow(empty_row)

    logger.success(f"Finished batch processing. Processed: {processed_count}/{len(pdf_files)} PDFs. Failed/Skipped: {failed_count}/{len(pdf_files)}. Results saved to: {output_csv_path}")

def process_specific_order_for_csv(order_path: Path, output_csv_path: Path):
    logger.info(f"Processing PDFs for a specific order directory: {order_path}")
    if not order_path.is_dir():
        logger.error(f"Specified order path is not a directory: {order_path}")
        return

    pdf_files = sorted(list(order_path.rglob("*.pdf")))
    if not pdf_files:
        logger.warning(f"No PDF files found in the specified order directory: {order_path}")
        return

    logger.info(f"Found {len(pdf_files)} PDF files in the order directory.")
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    processed_count = 0
    failed_count = 0
    with output_csv_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
        writer.writeheader()

        for pdf_path in pdf_files:
            extracted_data = process_single_pdf(pdf_path)
            if extracted_data:
                csv_row = prepare_csv_row(pdf_path, extracted_data)
                writer.writerow(csv_row)
                processed_count += 1
            else:
                logger.warning(f"Skipping CSV row for {pdf_path.name} due to missing data or extraction failure.")
                failed_count += 1
                empty_row = {field: "" for field in CSV_FIELDS}
                empty_row["PDF_Filename"] = pdf_path.name
                writer.writerow(empty_row)

    logger.success(f"Finished processing specific order. Processed: {processed_count}/{len(pdf_files)} PDFs. Failed/Skipped: {failed_count}/{len(pdf_files)}. Results saved to: {output_csv_path}")

if __name__ == "__main__":
    target_path_arg = None
    if len(sys.argv) > 1:
        target_path_arg = Path(sys.argv[1]).expanduser().resolve()

    output_csv_path = None

    if target_path_arg:
        if target_path_arg.is_file() and target_path_arg.suffix.lower() == ".pdf":
            logger.info(f"Processing a single PDF file: {target_path_arg}")
            output_csv_filename = f"single_pdf_result_{target_path_arg.stem}.csv"
            output_csv_path = Path(settings.OUTPUT_DIR) / output_csv_filename

            extracted_data = process_single_pdf(target_path_arg)
            if extracted_data:
                csv_row = prepare_csv_row(target_path_arg, extracted_data)
                with output_csv_path.open("w", newline="", encoding="utf-8") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
                    writer.writeheader()
                    writer.writerow(csv_row)
                print(f"\n✅ Single PDF processed. Result saved to: {output_csv_path}")
            else:
                print("\n❌ Single PDF processing failed or returned no data. Check logs.")

        elif target_path_arg.is_dir():
            logger.info(f"Processing all PDFs in a specific directory: {target_path_arg}")
            output_csv_filename = f"order_results_{target_path_arg.name}.csv"
            output_csv_path = Path(settings.OUTPUT_DIR) / output_csv_filename

            process_specific_order_for_csv(target_path_arg, output_csv_path)
            print(f"\n✅ Specific order directory processed. Results saved to: {output_csv_path}")

        else:
            print(f"Error: Argument '{target_path_arg}' is not a valid PDF file or directory.")
            sys.exit(1)
    else:
        logger.info("No specific path provided. Processing all PDFs under ELTEN_DATA_DIR.")
        output_csv_filename = "all_elten_data_batch_results.csv"
        output_csv_path = Path(settings.OUTPUT_DIR) / output_csv_filename

        process_directory_for_csv(settings.ELTEN_DATA_DIR, output_csv_path)
        print(f"\n✅ Batch processing complete for ELTEN_DATA_DIR. Results saved to: {output_csv_path}")

    print(f"\nDetailed processing logs can be found in: {settings.OUTPUT_DIR}/process.log")

import csv, sys
from pathlib import Path
from loguru import logger
from config import settings

# onze bestaande functies
from src.ocr_utils import extract_text_from_pdf_robust
from src.llm_extractor import extract_fields_with_llm

"""
Gebruik:
  python tools/run_batch.py /pad/naar/orders_root

Voorbeeld:
  python tools/run_batch.py data/Elten
Schrijft:
  outputs/llm_batch_results.csv
"""

def main(root: Path):
    pdfs = sorted(p for p in root.rglob("*.pdf"))
    if not pdfs:
        print(f"Geen PDF's gevonden onder: {root}")
        return

    out_csv = Path(settings.OUTPUT_DIR) / "llm_batch_results.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "PDF",
        "Tolerances_General","Tol_0_20","Tol_20_200","Tol_200_2000","Tol_gt_2000",
        "Welding_Designation","Weld_Finish","Post_Treatment","Material_Grade","Notes"
    ]

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()

        for pdf in pdfs:
            logger.info(f"[OCR+LLM] {pdf}")
            txt = extract_text_from_pdf_robust(str(pdf)) or ""
            data = extract_fields_with_llm(txt)

            row = {k: "" for k in fields}
            row["PDF"] = str(pdf)

            # vlakke tol-banden als aanwezig
            tol = (data or {}).get("Tolerances_Table") or {}
            bands = tol.get("bands") if isinstance(tol, dict) else {}
            row.update({
                "Tolerances_General": data.get("Tolerances_General"),
                "Tol_0_20": bands.get("0-20",""),
                "Tol_20_200": bands.get("20-200",""),
                "Tol_200_2000": bands.get("200-2000",""),
                "Tol_gt_2000": bands.get(">2000",""),
                "Welding_Designation": data.get("Welding_Designation"),
                "Weld_Finish": data.get("Weld_Finish"),
                "Post_Treatment": data.get("Post_Treatment"),
                "Material_Grade": data.get("Material_Grade"),
                "Notes": data.get("Notes"),
            })

            # nettere weergave voor lijsten
            if isinstance(row["Material_Grade"], (list, tuple)):
                row["Material_Grade"] = ", ".join(map(str, row["Material_Grade"]))
            if isinstance(row["Notes"], (list, tuple)):
                row["Notes"] = " | ".join(map(str, row["Notes"]))

            w.writerow(row)

    print(f"\n✅ Klaar. Resultaten: {out_csv}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Gebruik: python tools/run_batch.py /pad/naar/orders_root")
        sys.exit(1)
    main(Path(sys.argv[1]).expanduser().resolve())

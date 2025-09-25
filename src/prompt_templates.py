# src/prompt_templates.py

SYSTEM_INSTRUCTIONS = (
    "Je bent een uiterst precieze data-extractor voor technische tekeningen (metaal). "
    "Geef UITSLUITEND geldig JSON terug, zonder extra tekst of uitleg. "
    "Als een veld ontbreekt of onzeker is: null (of lege lijst voor Notes). "
    "Corrigeer evidente OCR-typo's alleen als de context 100% duidelijk is."
)

EXTRACT_DATA_PROMPT = """
Je krijgt hieronder OCR-tekst uit een tekening. Extraheer uitsluitend:
Tolerances_General, Tolerances_Table, Welding_Designation, Weld_Finish, Post_Treatment, Material_Grade, Notes

Zoekstrategie (belangrijk):
- Titelblok (rechtsonder) heeft de meeste labels/rijen.
- Labels (NL/EN): 
  * Toleranties, Tolerance(s), General tolerance, Afwijking, tol., ±
  * Weld/Welding/Las, Welding designation, EN ISO 2553 / DIN EN ISO 2553
  * Weld finish/Lasafwerking: Surface grind after welding, flush ground, dressed
  * Post-treatment/Nabehandeling/Afwerking/Surface treatment/Finish/Coating
  * Materiaal/Material/Material grade/Quality/Qualiteit
  * Notes/Remarks/Opmerkingen
- Material_Grade: alleen realistische materiaalnotaties (bijv. St.37, S235/S275/S355, 1.0038, 304/316/316L, 1.4301/1.4404, AlMg3, EN AW-5754/6082, DX51D, Q235/Q345).
- VERBOD: Negeer papierformaten/bladmaten (A0/A1/A2/A3/A4/A5), Sheet size, Scale, Bladnr., Revision.
- Post_Treatment: herken ook STANDALONE headers/opschriften buiten het titelblok (bv. grote tekst “Bead blasted” rechts onderin) en accepteer varianten:
  Bead blasted, Electro galvanized/Electrogalv, Hot-dip galvanized (HDG), Zinc plated,
  Powder coated/coating, Anodized, Painted (RAL ...).

Toleranties:
- Geef zowel een korte regel als JSON-tabel (mm) wanneer beschikbaar.
- De tabel-keys zijn typisch: "0-20", "20-200", "200-2000", ">2000" met waarden zoals "±0.2", "±0.5", "±1.0", "±2.0".
- Als geen tabel gevonden: zet Tolerances_Table = null.

Document (OCR-tekst):
---
{document_text}
---

Output (exact JSON, alleen deze keys):
{{
  "Tolerances_General": "... of null",
  "Tolerances_Table": {{"unit":"mm","bands":{{"0-20":"...","20-200":"...","200-2000":"...",">2000":"..."}}}}  or null,
  "Welding_Designation": "... of null",
  "Weld_Finish": "... of null",
  "Post_Treatment": "... of null",
  "Material_Grade": "... of null",
  "Notes": ["..."]  # lege lijst als niets gevonden
}}
"""

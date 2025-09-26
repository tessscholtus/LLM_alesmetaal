# src/prompt_templates.py
from string import Template

SYSTEM_INSTRUCTIONS = (
    "Je bent een uiterst precieze data-extractor voor technische tekeningen (metaal). "
    "Geef UITSLUITEND geldig JSON terug, zonder extra tekst of uitleg. "
    "Als een veld ontbreekt of onzeker is: null (of lege lijst voor Notes/Dimensions/Tolerances). "
    "Corrigeer evidente OCR-typo's alleen als de context 100% duidelijk is."
)

DIMENSION_STRUCTURE_HELP = """
Dimensions should be returned as a list of objects, each with:
  - "value": The numerical value (float or int).
  - "unit": The unit of measurement (e.g., "mm", inferred or stated).
  - "description": A brief text description of what the dimension refers to (e.g., "Length", "Width", "Height", "Offset", "Thread Size"). Infer this from labels or surrounding text.
  Example: [{"value": 366.0, "unit": "mm", "description": "Overall Length"}, {"value": 90.0, "unit": "mm", "description": "Offset to first pin"}]
"""

TOLERANCE_TABLE_STRUCTURE_HELP = """
Tolerances_Table: If a table of general tolerances is present, return it as a JSON object with:
  - "unit": The unit of measurement (e.g., "mm").
  - "bands": An object mapping dimension ranges to their tolerance values.
    - Keys: "0-20", "20-200", "200-2000", ">2000"
    - Values: The tolerance string (e.g., "±0.2").
  Example: {"unit": "mm", "bands": {"0-20": "±0.2", "20-200": "±0.5", "200-2000": "±1.0", ">2000": "±2.0"}}
If no explicit table is found, set this to null.
"""

# Let OP: GEEN f-string en GEEN .format placeholders meer in de body.
EXTRACT_DATA_PROMPT_TEMPLATE = Template("""
Je krijgt hieronder OCR-tekst uit een tekening. Extraheer uitsluitend:
Tolerances_General, Tolerances_Table, Welding_Designation, Weld_Finish, Post_Treatment, Material_Grade, Notes, Dimensions

Zoekstrategie (belangrijk):
- Titelblok (rechtsonder) heeft de meeste labels/rijen.
- Labels (NL/EN):
  * Toleranties, Tolerance(s), General tolerance, Afwijking, tol., ±
  * Weld/Welding/Las, Welding designation, EN ISO 2553 / DIN EN ISO 2553
  * Weld finish/Lasafwerking: Surface grind after welding, flush ground, dressed
  * Post-treatment/Nabehandeling/Afwerking/Surface treatment/Finish/Coating
  * Materiaal/Material/Material grade/Quality/Qualiteit
  * Notes/Remarks/Opmerkingen
  * Afmetingen (Dimensions): Zoek naar getallen met eenheden (mm) en bijbehorende labels/context (bv. "366", "90", "90.5", "M16"). M16 is een schroefdraad-afmeting.

- VERBOD: Negeer papierformaten/bladmaten (A0/A1/A2/A3/A4/A5), Sheet size, Scale, Bladnr., Revision.
- Post_Treatment: herken ook STANDALONE headers/opschriften buiten het titelblok (bv. grote tekst “Bead blasted” rechts onderin) en accepteer varianten:
  Bead blasted, Electro galvanized/Electrogalv, Hot-dip galvanized (HDG), Zinc plated,
  Powder coated/coating, Anodized, Painted (RAL ...).
- Weld_Finish: herken ook standalone opschriften zoals "Surface grind after welding".

Material_Grade: alleen realistische materiaalnotaties (bijv. St.37, S235/S275/S355, 1.0038, 304/316/316L, 1.4301/1.4404, AlMg3, EN AW-5754/6082, DX51D, Q235/Q345).

{DIMENSION_STRUCTURE_HELP}
{TOLERANCE_TABLE_STRUCTURE_HELP}

Document (OCR-tekst):
---
$document_text
---

Output (exact JSON, alleen deze keys):
{
  "Tolerances_General": "... of null",
  "Tolerances_Table": {"unit":"mm","bands":{"0-20":"...","20-200":"...","200-2000":"...",">2000":"..."}}  or null,
  "Welding_Designation": "... of null",
  "Weld_Finish": "... of null",
  "Post_Treatment": "... of null",
  "Material_Grade": "... of null",
  "Notes": ["..."],
  "Dimensions": []
}
""".replace("{DIMENSION_STRUCTURE_HELP}", DIMENSION_STRUCTURE_HELP)
  .replace("{TOLERANCE_TABLE_STRUCTURE_HELP}", TOLERANCE_TABLE_STRUCTURE_HELP))

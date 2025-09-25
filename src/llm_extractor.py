# src/llm_extractor.py — Gemini (Google AI Studio) + profiel-injectie
import json, re, time, os
import google.generativeai as genai
from loguru import logger
from .prompt_templates import SYSTEM_INSTRUCTIONS, EXTRACT_DATA_PROMPT
from .client_profile import load_profile
from config import settings

# Forceer REST (stabieler buiten GCP)
genai.configure(api_key=settings.GOOGLE_API_KEY, transport="rest")
MODEL_NAME = os.getenv("GEMINI_MODEL", settings.GEMINI_MODEL or "gemini-1.5-flash-8b")

TARGET_KEYS = [
    "Tolerances_General",
    "Welding_Designation",
    "Weld_Finish",
    "Post_Treatment",
    "Material_Grade",
    "Notes",
]

def _coerce_json(s: str) -> dict:
    s = (s or "").strip()
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r'\{[\s\S]*\}', s)
        if m:
            return json.loads(m.group(0))
        raise ValueError("Kon geen geldig JSON-object parsen uit LLM-output.")

def _normalize(data: dict) -> dict:
    out = {k: data.get(k) for k in TARGET_KEYS}
    # Lege strings -> None
    for k, v in out.items():
        if isinstance(v, str) and v.strip() == "":
            out[k] = None
    # Notes als lijst
    if out.get("Notes") is None:
        out["Notes"] = []
    elif isinstance(out["Notes"], str):
        parts = [p.strip() for p in re.split(r'[\n;]+', out["Notes"]) if p.strip()]
        out["Notes"] = parts
    # Papierformaten geen materiaal
    if isinstance(out.get("Material_Grade"), str) and out["Material_Grade"].strip().upper() in {"A0","A1","A2","A3","A4","A5"}:
        out["Material_Grade"] = None
    return out

def extract_fields_with_llm(document_text: str, max_chars: int = 1500) -> dict:
    """
    Neemt ruwe OCR-tekst en retourneert één dict met TARGET_KEYS.
    - max_chars laag houden = sneller/goedkoper/stabieler.
    - eenvoudige retry op netwerk/timeout.
    """
    empty = {k: None for k in TARGET_KEYS}; empty["Notes"] = []
    if not document_text or not document_text.strip():
        return empty

    # Context uit base (+ optioneel CLIENT=<naam> profiel)
    profile_json = load_profile()
    profile_block = f"CLIENT_PROFILE_JSON:\n{profile_json}\n\n" if profile_json else ""

    doc = document_text[:max_chars]
    prompt = SYSTEM_INSTRUCTIONS + "\n\n" + profile_block + EXTRACT_DATA_PROMPT.format(document_text=doc)

    model = genai.GenerativeModel(MODEL_NAME)

    # simpele retry
    last_err = None
    for attempt in range(3):
        try:
            resp = model.generate_content(prompt)
            text = (getattr(resp, "text", "") or "").strip()
            if not text:
                logger.warning("Lege LLM-respons.")
                return empty
            data = _coerce_json(text)
            return _normalize(data)
        except Exception as e:
            last_err = e
            wait = 1.5 * (attempt + 1)
            logger.warning(f"LLM-fout (attempt {attempt+1}/3): {e} — retry in {wait:.1f}s")
            time.sleep(wait)

    logger.error(f"LLM faalde na retries: {last_err}")
    return empty

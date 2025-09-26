# src/llm_extractor.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

from loguru import logger
import google.generativeai as genai

from .prompt_templates import SYSTEM_INSTRUCTIONS, EXTRACT_DATA_PROMPT_TEMPLATE
from .client_profile import load_profile
from config import settings

# ---------------------------
# Google Generative AI config
# ---------------------------
try:
    genai.configure(api_key=settings.GOOGLE_API_KEY, transport="rest")
except Exception as e:
    logger.error(f"Failed to configure Google Generative AI: {e}")
    logger.error("Ensure GOOGLE_API_KEY is set in your .env or environment variables.")

MODEL_NAME = os.getenv("GEMINI_MODEL", settings.GEMINI_MODEL or "gemini-1.5-flash-8b")

# ---------------------------
# Doelvelden (extern bruikbaar)
# ---------------------------
TARGET_KEYS: List[str] = [
    "Material_Grade",
    "Surface_Roughness",
    "Geometrical_Tolerancing",
    "Dimensional_Tolerancing",
    "Break_Sharp_Edges",
    "Retaining_Ring_Grooves_Sharp",
    "Welding_Notes",
    "Tolerances_General_Linear",
    "Tolerances_Machining",
    "Tolerances_Welded_Sheetmetal",
    "Welding_Designation",
    "Weld_Finish",
    "Post_Treatment",
    "Notes",
    "Drawing_Number",
    "Revision",
]

# ---------------------------
# Helpers
# ---------------------------
_PM_VARIANTS = re.compile(r"(±|\+/?-)", re.I)
_DEC_COMMA = re.compile(r"(\d+),(\d+)")
_MATERIAL_FORM_WORDS = re.compile(r"\b(sheet|plate|round\s*bar|square\s*bar|flat\s*bar|tube|pipe)\b", re.I)

def _norm_pm(s: str) -> str:
    if not s:
        return s
    s2 = _DEC_COMMA.sub(r"\1.\2", s)
    s2 = _PM_VARIANTS.sub("±", s2)
    return s2.strip()

def _coerce_json(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    if not s:
        logger.warning("Received empty string for JSON coercion.")
        return {}
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        logger.warning("LLM output was not valid JSON. Attempting to extract a JSON block...")
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        logger.error("No JSON block found in LLM output string.")
        raise ValueError("Could not find any JSON structure in LLM output.")
    blk = m.group(0)
    try:
        logger.debug(f"Found potential JSON block (first 200 chars): {blk[:200]}...")
        return json.loads(blk)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON block found in LLM output: {e}")
        raise ValueError("Could not parse LLM output as JSON even after block extraction.") from e

def _pick(s: Any, *paths: str) -> Any:
    """Safely pick from nested dict via dotted paths; returns None if missing."""
    if not isinstance(s, dict):
        return None
    for p in paths:
        cur = s
        ok = True
        for key in p.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok:
            return cur
    return None

def _clean_welding_notes(notes: List[str]) -> List[str]:
    seen = set()
    out = []
    for n in notes or []:
        if not n:
            continue
        t = re.sub(r"\s+", " ", str(n)).strip()
        tl = t.lower()
        if tl not in seen:
            out.append(t)
            seen.add(tl)
    return out

def _extract_booleans(raw_text: str) -> Dict[str, bool]:
    lt = raw_text.lower()
    break_edges = bool(re.search(r"break sharp edges|scherpe kanten breken|deburr edges|remove sharp edges", lt))
    grooves_sharp = bool(re.search(r"retaining ring grooves sharp|seegerring-?groeven scherp|keep ring grooves sharp", lt))
    return {
        "Break_Sharp_Edges": break_edges,
        "Retaining_Ring_Grooves_Sharp": grooves_sharp,
    }

def _normalize_tables(obj: Any) -> Dict[str, Any] | None:
    if not isinstance(obj, dict):
        return None
    unit = str(obj.get("unit", "mm")).strip().lower() or "mm"
    bands = obj.get("bands", {}) or {}
    out_bands: Dict[str, str] = {}
    for k, v in bands.items():
        if not isinstance(v, str):
            continue
        val = _norm_pm(v)
        # accept canonical keys or pass-through; caller should map headers to correct table
        out_bands[k] = val
    return {"unit": unit, "bands": out_bands} if out_bands else {"unit": unit, "bands": {}}

def _normalize(data: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {k: data.get(k) for k in TARGET_KEYS}

    # --- strings cleanup / lists
    for k, v in list(out.items()):
        if v is None:
            continue
        if isinstance(v, str):
            vv = v.replace("\r", " ").replace("\n", " ").strip()
            out[k] = vv if vv else None
        elif isinstance(v, list):
            out[k] = [re.sub(r"\s+", " ", str(x)).strip() for x in v if str(x).strip()]

    # --- Material_Grade: strip form words and pull material from notes if missing
    if isinstance(out.get("Material_Grade"), str):
        mg = out["Material_Grade"]
        mg_clean = _MATERIAL_FORM_WORDS.sub("", mg).strip(" -_,")
        out["Material_Grade"] = mg_clean if mg_clean else None

    if not out.get("Material_Grade"):
        # Try to infer simple grades from notes/free text (e.g., 'Side guide 304', 'A2 Round Bar')
        text = raw_text
        m = re.search(r"\b(304L?|316L?|A2|A4|S\s*\d{3}|1\.\d{4}|EN\s*AW-\d+|AlMg\d)\b", text, re.I)
        if m:
            grade = m.group(1).upper().replace(" ", "")
            grade = grade.replace("S", "S")  # noop; kept for symmetry
            out["Material_Grade"] = grade

    # --- Post_Treatment whitelist sanity: if looks like material, swap
    if out.get("Post_Treatment"):
        pt = out["Post_Treatment"]
        if re.search(r"\b(304L?|316L?|A2|A4|S\s*\d{3}|1\.\d{4}|EN\s*AW-\d+|AlMg\d)\b", pt, re.I):
            if not out.get("Material_Grade"):
                out["Material_Grade"] = re.search(r"\b(304L?|316L?|A2|A4|S\s*\d{3}|1\.\d{4}|EN\s*AW-\d+|AlMg\d)\b", pt, re.I).group(1)
            out["Post_Treatment"] = None

    # --- Welding_Notes vs Welding_Designation
    if out.get("Welding_Notes"):
        out["Welding_Notes"] = _clean_welding_notes(out["Welding_Notes"])
    # If Welding_Designation contains a freeform sentence, move it to notes
    if out.get("Welding_Designation"):
        if re.search(r"\b(weld|grind|smooth|finish|corner|length|stitch|continuous)\b", out["Welding_Designation"], re.I):
            w = out.get("Welding_Notes") or []
            w.append(out["Welding_Designation"])
            out["Welding_Notes"] = _clean_welding_notes(w)
            out["Welding_Designation"] = None

    # --- Booleans from raw text (fallback/enrichment)
    bools = _extract_booleans(raw_text)
    for k, v in bools.items():
        if out.get(k) is None:
            out[k] = v

    # --- Surface_Roughness direct sanity
    sr = out.get("Surface_Roughness")
    if isinstance(sr, dict):
        # normalize units/parameter/value formatting
        if isinstance(sr.get("unit"), str):
            u = sr["unit"].replace("μ", "µ")
            u = "µm" if u.lower() in {"um", "µm", "μm"} else sr["unit"]
            sr["unit"] = u
        if isinstance(sr.get("value"), str):
            sr["value"] = _DEC_COMMA.sub(r"\1.\2", sr["value"]).strip()
        if isinstance(sr.get("parameter"), str):
            sr["parameter"] = sr["parameter"].strip()
        if isinstance(sr.get("standard"), str):
            sr["standard"] = re.sub(r"\s+", " ", sr["standard"]).strip()
        out["Surface_Roughness"] = sr
    elif sr is not None and not isinstance(sr, dict):
        out["Surface_Roughness"] = None

    # --- Geometrical/Dimensional standards: trim
    for key in ("Geometrical_Tolerancing", "Dimensional_Tolerancing"):
        obj = out.get(key)
        if isinstance(obj, dict):
            if isinstance(obj.get("standard"), str):
                obj["standard"] = re.sub(r"\s+", " ", obj["standard"]).strip()
            if isinstance(obj.get("scope"), str):
                obj["scope"] = re.sub(r"\s+", " ", obj["scope"]).strip()
            out[key] = obj
        else:
            if obj is not None:
                out[key] = None

    # --- Tolerance tables: normalize bands and map legacy single table if present
    for key in ("Tolerances_General_Linear", "Tolerances_Machining", "Tolerances_Welded_Sheetmetal"):
        if out.get(key):
            out[key] = _normalize_tables(out[key])

    # Legacy support: if older LLM returned Tolerances_Table, map to General_Linear
    legacy = data.get("Tolerances_Table")
    if legacy and not out.get("Tolerances_General_Linear"):
        out["Tolerances_General_Linear"] = _normalize_tables(legacy)

    # --- Normalize all bands to '±x.x' decimal point
    def norm_table(tbl: Dict[str, Any] | None) -> Dict[str, Any] | None:
        if not isinstance(tbl, dict):
            return None
        bands = tbl.get("bands") or {}
        out_b = {}
        for k, v in bands.items():
            out_b[k] = _norm_pm(str(v)) if v is not None else v
        unit = tbl.get("unit", "mm") or "mm"
        return {"unit": str(unit).strip().lower(), "bands": out_b}
    for key in ("Tolerances_General_Linear", "Tolerances_Machining", "Tolerances_Welded_Sheetmetal"):
        out[key] = norm_table(out.get(key)) if out.get(key) else None

    # --- Drawing number & revision (simple heuristics)
    if not out.get("Drawing_Number"):
        m = re.search(r"(?:Drawing\s*number|Tekening(?:\s*nummer)?)\s*[:\-]?\s*([A-Za-z0-9_\-\/\.]+)", raw_text, re.I)
        if m:
            out["Drawing_Number"] = m.group(1).strip()
    if not out.get("Revision"):
        m = re.search(r"(?:Rev(?:ision)?|Revisie)\s*[:\-]?\s*([A-Za-z0-9_\-\.]+)", raw_text, re.I)
        if m:
            out["Revision"] = m.group(1).strip()

    # --- Notes ensure list
    if out.get("Notes") is None:
        out["Notes"] = []
    elif isinstance(out["Notes"], str):
        out["Notes"] = [out["Notes"].strip()] if out["Notes"].strip() else []

    return out

# ---------------------------
# Hoofdfunctie
# ---------------------------
def extract_fields_with_llm(document_text: str, max_chars: int = 20000) -> Dict[str, Any]:
    """
    Neemt OCR-tekst en vraagt de LLM om strikt JSON terug te geven met TARGET_KEYS.
    Retourneert een genormaliseerde dict (alle keys aanwezig).
    """
    empty_result: Dict[str, Any] = {k: None for k in TARGET_KEYS}
    empty_result["Welding_Notes"] = []
    empty_result["Notes"] = []

    if not document_text or not document_text.strip():
        logger.warning("Received empty OCR text. Returning empty result.")
        return empty_result

    truncated_text = document_text[:max_chars] if len(document_text) > max_chars else document_text

    # Optioneel profielblok
    try:
        profile_json = load_profile()  # JSON-string of ""
        profile_block = f"CLIENT_PROFILE_JSON:\n{profile_json}\n\n" if profile_json else ""
        if profile_json:
            logger.debug("Client profile loaded and injected into prompt.")
    except Exception as e:
        logger.warning(f"Could not load client profile: {e}. Proceeding without profile.")
        profile_block = ""

    # Bouw prompt
    try:
        prompt_body = EXTRACT_DATA_PROMPT_TEMPLATE.substitute(document_text=truncated_text)
        full_prompt = SYSTEM_INSTRUCTIONS + "\n\n" + profile_block + prompt_body
    except Exception as e:
        logger.error(f"Error building the LLM prompt: {e}")
        return empty_result

    # LLM call met retry
    model = genai.GenerativeModel(MODEL_NAME)
    last_err = None
    response_text = ""

    for attempt in range(3):
        try:
            logger.debug(f"Calling LLM (Attempt {attempt + 1}/3) with prompt length: {len(full_prompt)} chars.")
            response = model.generate_content(full_prompt)

            if getattr(response, "prompt_feedback", None) and getattr(response.prompt_feedback, "block_reason", None):
                block_reason = response.prompt_feedback.block_reason
                logger.warning(f"LLM prompt blocked due to safety reasons: {block_reason}. Attempt {attempt + 1}/3.")
                continue

            if getattr(response, "candidates", None) and response.candidates and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text or ""
            else:
                response_text = ""
                logger.warning("LLM returned an empty or unexpected response candidate structure.")

            if not response_text.strip():
                logger.warning(f"LLM returned empty response text. Attempt {attempt + 1}/3.")
                continue

            logger.debug(f"LLM raw response (first 200 chars): {response_text[:200]}...")
            data = _coerce_json(response_text)
            normalized = _normalize(data, raw_text=truncated_text)
            return normalized

        except json.JSONDecodeError as e:
            last_err = f"JSON Decode Error: {e}. Raw response: {response_text[:200]}..."
            logger.warning(f"LLM JSON Decode Error (Attempt {attempt + 1}/3): {e}")
        except ValueError as e:
            last_err = f"Value Error during JSON coercion: {e}. Raw response: {response_text[:200]}..."
            logger.warning(f"LLM Value Error (Attempt {attempt + 1}/3): {e}")
        except Exception as e:
            last_err = f"General LLM API Error: {e}"
            logger.warning(f"General LLM Error (Attempt {attempt + 1}/3): {e}")

        wait_time = 1.5 * (attempt + 1)
        logger.info(f"Retrying LLM call in {wait_time:.1f} seconds...")
        time.sleep(wait_time)

    logger.error(f"LLM extraction failed after 3 attempts. Last error: {last_err}")
    return empty_result

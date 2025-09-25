import json, pathlib, os
try:
    import yaml  # pyyaml
except ImportError:
    yaml = None

BASE_PATH = pathlib.Path("profiles/base.yaml")

def _read_yaml(p: pathlib.Path):
    if not p.exists() or yaml is None:
        return {}
    return yaml.safe_load(p.read_text()) or {}

def load_profile() -> str:
    """
    Laadt base-profiel + optioneel klant-profiel uit env CLIENT (profiles/<client>.yaml).
    Geeft compacte JSON-string terug voor in de prompt (of "" als niets).
    """
    base = _read_yaml(BASE_PATH)
    client_name = os.getenv("CLIENT", "").strip().lower()
    merged = dict(base)

    if client_name:
        p = pathlib.Path(f"profiles/{client_name}.yaml")
        client = _read_yaml(p)
        # eenvoudige shallow-merge (genoeg voor labels/whitelists e.d.)
        for k, v in (client or {}).items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k].update(v)
            else:
                merged[k] = v

    if not merged:
        return ""
    return json.dumps(merged, ensure_ascii=False)

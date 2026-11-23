"""Lecture / ecriture du fichier ``config.json`` (reglages machine).

Le fichier est volontairement tolerant : les cles inconnues sont ignorees,
les valeurs manquantes reprennent les valeurs par defaut, et les types sont
coerces (un ``"180"`` texte devient bien un float).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .models import CONFIG_FIELDS, CORNER_STYLES, MachineConfig

CONFIG_FILENAME = "config.json"

# Valeurs par defaut issues du modele (source de verite unique).
DEFAULTS: dict = MachineConfig().as_dict()

# Bornes des champs numeriques : protege l'interface si config.json est edite
# a la main (Streamlit refuse une valeur hors des min/max d'un widget).
BOUNDS: dict[str, tuple[float, float]] = {
    "plate_w_mm": (50.0, 600.0),
    "plate_h_mm": (50.0, 600.0),
    "margin_mm": (0.0, 60.0),
    "spacing_mm": (0.0, 30.0),
    "border_mm": (0.0, 15.0),
    "simplify_mm": (0.0, 1.5),
    "calib_x_mm": (0.0, 400.0),
    "calib_y_mm": (0.0, 400.0),
    "offset_x_mm": (-30.0, 30.0),
    "offset_y_mm": (-30.0, 30.0),
    "z_cut_mm": (0.0, 150.0),
    "z_travel_mm": (0.5, 150.0),
    "feed_cut": (100, 12000),
    "feed_travel": (100, 20000),
    "plunge_feed": (50, 5000),
}


def config_path(base_dir: Path | str | None = None) -> Path:
    """Chemin du config.json (racine du projet par defaut)."""
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    return root / CONFIG_FILENAME


def _coerce(key: str, value):
    """Force le type de ``value`` sur celui de la valeur par defaut."""
    default = DEFAULTS[key]
    try:
        if isinstance(default, bool):
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "oui", "on")
            return bool(value)
        if isinstance(default, int):
            return int(round(float(value)))
        if isinstance(default, float):
            return float(value)
        return str(value)
    except (TypeError, ValueError):
        return default


def sanitize(data: dict | None, base: dict | None = None) -> dict:
    """Filtre / complete / convertit un dict de reglages."""
    result = dict(DEFAULTS if base is None else base)
    if not isinstance(data, dict):
        return result
    for key in CONFIG_FIELDS:
        if key in data:
            result[key] = _coerce(key, data[key])
    for key, (low, high) in BOUNDS.items():
        result[key] = max(low, min(high, result[key]))
    if result.get("corner_style") not in CORNER_STYLES:
        result["corner_style"] = DEFAULTS["corner_style"]
    result["bg_color"] = _normalize_color(result.get("bg_color"))
    return result


def _normalize_color(value) -> str:
    """Force une couleur '#RRGGBB' valide (sinon valeur par defaut)."""
    text = str(value or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", text):
        text = "#" + "".join(char * 2 for char in text[1:])
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    return DEFAULTS["bg_color"]


def read_config(path: Path | str | None = None) -> dict:
    """Charge config.json ; retourne les valeurs par defaut s'il est absent/casse."""
    p = Path(path) if path else config_path()
    try:
        with p.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return sanitize(data)


def write_config(values: dict, path: Path | str | None = None) -> Path:
    """Ecrit config.json et retourne son chemin."""
    p = Path(path) if path else config_path()
    clean = sanitize(values)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return p


def config_json_bytes(values: dict) -> bytes:
    """config.json en memoire (pour le bouton de telechargement)."""
    clean = sanitize(values)
    return (json.dumps(clean, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

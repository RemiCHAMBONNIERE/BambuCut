"""Lecteur anime de la trajectoire de decoupe (composant Streamlit local).

Le composant HTML (``cut_component/index.html``) superpose au PNG d'apercu le
tracé réel du G-code : déplacements en gris puis contours en rouge, dans l'ordre
où la machine les exécute. Il ne renvoie aucune valeur à Streamlit : il sert
uniquement à vérifier visuellement la planche avant de lancer une découpe.

Les étapes sont calculées par :func:`bambucut.gcode.iter_cut_contours`, donc le
lecteur et le G-code partagent exactement la même séquence (offsets compris).
Les durées de chaque phase sont calculées aux vitesses réelles configurées, pour
que « 1× » corresponde au temps estimé affiché. Aucun npm, aucun réseau : le
dossier est servi tel quel par Streamlit.
"""

from __future__ import annotations

import base64
from pathlib import Path

from .gcode import iter_cut_contours
from .models import MachineConfig
from .packing import Sheet

COMPONENT_DIR = Path(__file__).resolve().parent / "cut_component"

_component = None


def _get_component():
    """Déclare le composant au premier appel (nécessite un ScriptRunContext)."""
    global _component
    if _component is None:
        import streamlit.components.v1 as components

        _component = components.declare_component(
            "bambucut_cut_player", path=str(COMPONENT_DIR)
        )
    return _component


def png_data_url(png: bytes) -> str:
    """Data URL d'un PNG, pour l'afficher dans l'iframe sans fichier temporaire."""
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def _seconds(mm: float, feed_mm_min: float) -> float:
    """Temps reel (s) pour parcourir ``mm`` a ``feed_mm_min`` mm/min."""
    return max(0.0, float(mm)) / max(1.0, float(feed_mm_min)) * 60.0


def step_durations(cfg: MachineConfig, travel_mm: float, length_mm: float) -> tuple[int, int]:
    """Durees (ms) d'un deplacement et de la coupe qui suit, aux vitesses reglees.

    La descente et la remontee de lame sont ajoutees a la coupe : c'est la ou
    la lame reste sur le contour. Le lecteur anime ainsi le trajet complet a
    vitesse reelle (1x = G-code), sans minimum artificial.
    """
    z_move = max(0.0, float(cfg.z_travel_mm) - float(cfg.z_cut_mm))
    travel_s = _seconds(travel_mm, cfg.feed_travel)
    cut_s = _seconds(length_mm, cfg.feed_cut)
    cut_s += _seconds(z_move, cfg.plunge_feed)
    cut_s += _seconds(z_move, cfg.feed_travel)
    return round(travel_s * 1000), round(cut_s * 1000)


def cut_steps(sheet: Sheet, cfg: MachineConfig) -> list[dict]:
    """Étapes du trajet, dans l'ordre du G-code, avec offsets appliqués."""
    steps: list[dict] = []
    for item in iter_cut_contours(sheet, cfg):
        points = [
            [round(float(x), 3), round(float(y), 3)] for (x, y) in item["points"]
        ]
        # Le G-code referme chaque contour : on ajoute le premier point en fin
        # pour que le lecteur montre exactement le meme tracé (et que la lame
        # revienne bien a son point de depart).
        if points:
            points.append(list(points[0]))
        travel = None
        if item["travel_from"] is not None:
            travel = [
                [round(float(item["travel_from"][0]), 3), round(float(item["travel_from"][1]), 3)],
                points[0],
            ]
        travel_ms, cut_ms = step_durations(
            cfg, float(item["travel_mm"]), float(item["length_mm"])
        )
        steps.append(
            {
                "points": points,
                "travel": travel,
                "length_mm": round(float(item["length_mm"]), 2),
                "travel_mm": round(float(item["travel_mm"]), 2),
                "travel_ms": travel_ms,
                "cut_ms": cut_ms,
                "sticker": int(item["sticker_index"]),
                "contour": int(item["contour_index"]),
                "contour_total": int(item["contour_count"]),
                "name": str(item["name"])[:48],
            }
        )
    return steps


def estimate_seconds(steps: list[dict], cfg: MachineConfig) -> float:
    """Duree reelle du trajet anime a 1x (deplacements, Z et coupe inclus)."""
    total_ms = 0.0
    for step in steps:
        if "cut_ms" in step and "travel_ms" in step:
            total_ms += float(step["cut_ms"]) + float(step["travel_ms"])
        else:  # resultats autrefois mis en cache : calcul de repli
            travel_ms, cut_ms = step_durations(
                cfg,
                float(step.get("travel_mm") or 0.0),
                float(step.get("length_mm") or 0.0),
            )
            total_ms += travel_ms + cut_ms
    return round(total_ms / 1000.0, 1)


def render_cut_player(
    preview_png: bytes,
    steps: list[dict],
    plate_w: float,
    plate_h: float,
    calib_x: float,
    calib_y: float,
    cut_seconds: float,
    sheet: int,
    theme: str,
    key: str,
) -> None:
    """Affiche le lecteur anime d'une planche."""
    _get_component()(
        image=png_data_url(preview_png),
        steps=steps,
        plate_w=float(plate_w),
        plate_h=float(plate_h),
        calib_x=float(calib_x),
        calib_y=float(calib_y),
        cut_seconds=float(cut_seconds),
        sheet=int(sheet),
        theme=str(theme),
        key=key,
        default=None,
    )

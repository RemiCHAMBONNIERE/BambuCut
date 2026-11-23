"""Editeur interactif de planche (composant Streamlit local, sans npm).

Le composant HTML (``editor_component/index.html``) affiche les stickers d'une
planche a l'echelle et permet de les deplacer a la souris et de les
redimensionner par les poignees d'angle. Il ne renvoie a Streamlit qu'un facteur
d'echelle par image et un centre (mm) par sticker deplace : le calcul des tailles
finales (``scaled_size_mm``) et la reconstruction de la planche
(``sheets_from_layout``) restent cote Python.

Le protocole de composant est implemente a la main : aucune compilation, aucun
paquet npm, aucun acces reseau. Le dossier ``editor_component`` est servi tel
quel par Streamlit.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

COMPONENT_DIR = Path(__file__).resolve().parent / "editor_component"

_component = None


def _get_component():
    """Declare le composant au premier appel (necessite un ScriptRunContext)."""
    global _component
    if _component is None:
        import streamlit.components.v1 as components

        _component = components.declare_component(
            "bambucut_sheet_editor", path=str(COMPONENT_DIR)
        )
    return _component


def thumbnail_data_url(image: Image.Image, max_px: int = 200) -> str:
    """Vignette PNG (data URL) pour l'editeur : legere et transparente."""
    thumb = image.copy()
    thumb.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    thumb.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return "data:image/png;base64," + encoded


def editor_items(
    placements: list[dict], thumbs: dict[str, str], sheet: int = 1
) -> list[dict]:
    """Donnees JSON envoyees au composant.

    ``placements`` contient un dict par sticker pose (``uid``, ``name``, ``x``,
    ``y`` = coin bas-gauche en mm, ``w``, ``h`` = taille generee en mm,
    ``rotated`` = sticker tourne de 90 deg). Chaque sticker recoit un ``id``
    stable (``planche:position``) qui sert au composant a renvoyer sa position.
    """
    items = []
    for index, placement in enumerate(placements):
        uid = str(placement.get("uid") or "")
        items.append(
            {
                "id": str(placement.get("id") or f"{int(sheet)}:{index}"),
                "uid": uid,
                "name": str(placement.get("name") or "sticker"),
                "x": float(placement.get("x") or 0.0),
                "y": float(placement.get("y") or 0.0),
                "w": float(placement.get("w") or 0.0),
                "h": float(placement.get("h") or 0.0),
                "rotated": bool(placement.get("rotated")),
                "img": thumbs.get(uid, ""),
            }
        )
    return items


def sheet_editor(
    items: list[dict],
    plate_w: float,
    plate_h: float,
    sheet: int,
    total: int,
    gen: str,
    key: str,
    usable: dict | None = None,
    theme: str = "sober",
) -> dict | None:
    """Affiche l'editeur et retourne sa derniere valeur (``None`` au depart).

    ``usable`` decrit la zone utile (x0, y0, w, h en mm) dans laquelle les
    stickers doivent rester : le composant y borne le deplacement et la taille.
    ``theme`` habille le composant comme le reste de l'application.
    """
    kwargs = {}
    if usable:
        kwargs["usable"] = {
            "x0": float(usable.get("x0") or 0.0),
            "y0": float(usable.get("y0") or 0.0),
            "w": float(usable.get("w") or 0.0),
            "h": float(usable.get("h") or 0.0),
        }
    return _get_component()(
        items=items,
        plate_w=float(plate_w),
        plate_h=float(plate_h),
        sheet=int(sheet),
        total=int(total),
        gen=str(gen),
        theme=str(theme),
        key=key,
        default=None,
        **kwargs,
    )

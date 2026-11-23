"""Traitement d'image : PNG transparent -> silhouette -> bordure -> contour.

Chaine de traitement (toutes les unites internes sont en millimetres) :

1. lecture du PNG, conversion RVBA ;
2. recadrage sur la boite englobante du canal alpha ;
3. redimensionnement a 300 DPI selon la dimension demandee (ratio conserve) ;
4. detection de la silhouette avec OpenCV (canal alpha) ;
5. fusion des morceaux et remplissage des trous internes ;
6. buffer geometrique de ``border_mm`` (Shapely) ;
7. simplification Douglas-Peucker (``simplify_mm``) ;
8. rendu d'une image RVBA dont la taille = boite englobante du contour.
"""

from __future__ import annotations

from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .models import (
    CORNER_SHARP,
    MachineConfig,
    PreparedSticker,
    Point,
    parse_hex_color,
    resolve_bg_color,
)

PRINT_DPI = 300
MM_PER_INCH = 25.4
PX_PER_MM = PRINT_DPI / MM_PER_INCH  # ~11.811 px/mm

# Seuils de nettoyage.
_MIN_ALPHA_BBOX = 8       # alpha > 8 : pixel "visible" pour le recadrage
_ALPHA_CUT = 127          # alpha > 127 : silhouette de decoupe
_MIN_CONTOUR_MM2 = 0.15   # ignore les poussieres de pixel avant buffer
_MIN_PART_MM2 = 0.5       # ignore les morceaux minuscules apres buffer
_SMOOTH_MM = 0.12         # fermeture morphologique legere (anti-escalier)


class GeometryError(ValueError):
    """Erreur de traitement d'image (message directement affichable)."""


def _alpha_bbox(alpha: np.ndarray) -> tuple[int, int, int, int] | None:
    """Boite englobante des pixels visibles (x0, y0, x1, y1) ou None."""
    ys, xs = np.nonzero(alpha > _MIN_ALPHA_BBOX)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _iter_polygons(geom):
    """Itere sur les Polygon d'une geometrie Shapely quelconque."""
    if geom is None or geom.is_empty:
        return
    if geom.geom_type == "Polygon":
        yield geom
    elif hasattr(geom, "geoms"):
        for part in geom.geoms:
            yield from _iter_polygons(part)


def _clean_polygon(poly: Polygon) -> Polygon | None:
    """Valide un polygone et supprime ses trous internes."""
    if poly is None or poly.is_empty:
        return None
    if not poly.is_valid:
        poly = poly.buffer(0)
    result: list[Polygon] = []
    for part in _iter_polygons(poly):
        filled = Polygon(part.exterior)
        if not filled.is_empty and filled.area > 0:
            result.append(filled)
    if not result:
        return None
    return unary_union(result)


def _dedupe_points(points: list[Point], tolerance: float = 0.02) -> list[Point]:
    """Retire les doublons / points trop proches d'une polyligne."""
    clean: list[Point] = []
    for x, y in points:
        if not clean:
            clean.append((float(x), float(y)))
            continue
        px, py = clean[-1]
        if abs(x - px) > tolerance or abs(y - py) > tolerance:
            clean.append((float(x), float(y)))
    # Fermeture : le dernier point ne doit pas doubler le premier.
    if len(clean) > 1:
        fx, fy = clean[0]
        lx, ly = clean[-1]
        if abs(fx - lx) <= tolerance and abs(fy - ly) <= tolerance:
            clean.pop()
    return clean


def prepare_sticker(
    png_bytes: bytes,
    name: str,
    mode: str,
    size_mm: float,
    border_mm: float,
    simplify_mm: float,
    corner_style: str = "round",
    bg_color: str | None = None,
    uid: str = "",
) -> PreparedSticker:
    """Transforme un PNG en sticker pret a placer (image + contours en mm).

    Parameters
    ----------
    mode : "width" ou "height"
        Dimension pilote par ``size_mm`` ; l'autre est deduite du ratio.
    bg_color : str | None
        Couleur de fond (``#RRGGBB``). Si renseignee, toute la forme decoupee
        (bordure comprise) est remplie avec cette couleur, puis le visuel est
        pose par-dessus. ``None`` = fond transparent (papier).
    uid : str
        Identifiant de l'image d'origine (permet de retrouver un sticker dans
        l'editeur d'apercu, y compris apres rotation).
    """
    if mode not in ("width", "height"):
        raise GeometryError("Mode de dimension invalide (attendu : width/height).")
    if size_mm <= 0:
        raise GeometryError("La dimension demandee doit etre superieure a 0 mm.")
    if border_mm < 0:
        raise GeometryError("La bordure ne peut pas etre negative.")

    # --- 1. Lecture -----------------------------------------------------
    try:
        src = Image.open(BytesIO(png_bytes))
        src.load()
        src = ImageOps.exif_transpose(src)
    except Exception as exc:  # pragma: no cover - message utilisateur
        raise GeometryError(f"Image illisible : {exc}") from exc

    src = src.convert("RGBA")
    alpha_full = np.asarray(src.getchannel("A"), dtype=np.uint8)
    has_alpha = bool(alpha_full.min() < 250)

    # --- 2. Recadrage sur le contenu visible ----------------------------
    bbox = _alpha_bbox(alpha_full)
    if bbox is None:
        raise GeometryError(f"« {name} » est entierement transparente.")
    src = src.crop(bbox)
    src_w, src_h = src.size
    if src_w < 2 or src_h < 2:
        raise GeometryError(f"« {name} » est trop petite apres recadrage.")

    # --- 3. Redimensionnement 300 DPI, ratio strictement conserve ------
    aspect = src_w / src_h
    if mode == "width":
        target_w_mm = float(size_mm)
        target_h_mm = float(size_mm) / aspect
    else:
        target_h_mm = float(size_mm)
        target_w_mm = float(size_mm) * aspect

    px_w = max(1, int(round(target_w_mm * PX_PER_MM)))
    px_h = max(1, int(round(target_h_mm * PX_PER_MM)))
    # Garde-fou memoire (200 mm a 600 DPI = 4724 px ; on reste large).
    if max(px_w, px_h) > 8000:
        factor = 8000 / max(px_w, px_h)
        px_w = max(1, int(px_w * factor))
        px_h = max(1, int(px_h * factor))

    img = src.resize((px_w, px_h), Image.Resampling.LANCZOS)
    img_h_mm = px_h / PX_PER_MM

    # --- 4. Silhouette ---------------------------------------------------
    if has_alpha:
        alpha = np.asarray(img.getchannel("A"), dtype=np.uint8)
        mask = np.where(alpha > _ALPHA_CUT, 255, 0).astype(np.uint8)
    else:
        # Pas de transparence : on prend le rectangle exterieur de l'image.
        mask = np.full((px_h, px_w), 255, dtype=np.uint8)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise GeometryError(f"Impossible de detecter la silhouette de « {name} ».")

    pieces: list[Polygon] = []
    for contour in contours:
        if contour is None or len(contour) < 3:
            continue
        # Repere image (Y vers le bas) -> repere mm bas-gauche (Y vers le haut).
        pts = [
            (float(px) / PX_PER_MM, (px_h - 1 - float(py)) / PX_PER_MM)
            for px, py in contour.reshape(-1, 2)
        ]
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        for part in _iter_polygons(poly):
            if part.area >= _MIN_CONTOUR_MM2:
                pieces.append(Polygon(part.exterior))

    if not pieces:
        raise GeometryError(
            f"« {name} » ne contient pas de zone opaque assez grande pour etre decoupee."
        )

    merged = unary_union(pieces)
    if _SMOOTH_MM > 0:
        # Fermeture douce : gomme les micro-escaliers du masque binaire.
        merged = merged.buffer(_SMOOTH_MM, quad_segs=4).buffer(
            -_SMOOTH_MM, quad_segs=4
        )
    merged = _clean_polygon(merged)
    if merged is None or merged.is_empty:
        raise GeometryError(f"Contour vide apres nettoyage pour « {name} ».")

    # --- 5. Bordure blanche (buffer geometrique exact) ------------------
    join_style = 2 if corner_style == CORNER_SHARP else 1
    buffered_parts = []
    for part in _iter_polygons(merged):
        if border_mm > 0:
            grown = part.buffer(
                border_mm,
                quad_segs=10,
                join_style=join_style,
                mitre_limit=4.0,
            )
        else:
            grown = part
        for piece in _iter_polygons(grown):
            filled = Polygon(piece.exterior)
            if filled.area > 0:
                buffered_parts.append(filled)

    grown = unary_union(buffered_parts)
    grown_parts = sorted(_iter_polygons(grown), key=lambda p: p.area, reverse=True)
    if not grown_parts:
        raise GeometryError(f"Bordure impossible a calculer pour « {name} ».")

    # --- 6. Simplification Douglas-Peucker -----------------------------
    largest_area = grown_parts[0].area
    min_area = max(_MIN_PART_MM2, largest_area * 0.002)
    outlines: list[list[Point]] = []
    bounds: list[tuple[float, float, float, float]] = []

    for part in grown_parts:
        if part.area < min_area:
            continue
        simplified = part.simplify(max(0.0, simplify_mm), preserve_topology=True)
        if simplified.is_empty:
            continue
        if not simplified.is_valid:
            simplified = simplified.buffer(0)
        for piece in _iter_polygons(simplified):
            if piece.area < min_area:
                continue
            ring = _dedupe_points(list(piece.exterior.coords))
            if len(ring) < 3:
                continue
            outlines.append(ring)
            bounds.append(piece.bounds)

    if not outlines:
        raise GeometryError(f"Contour final vide pour « {name} ».")

    # --- 7. Image finale = boite englobante du contour -----------------
    minx = min(b[0] for b in bounds)
    miny = min(b[1] for b in bounds)
    maxx = max(b[2] for b in bounds)
    maxy = max(b[3] for b in bounds)
    box_w = maxx - minx
    box_h = maxy - miny
    if box_w <= 0 or box_h <= 0:
        raise GeometryError(f"Boite englobante invalide pour « {name} ».")

    local_outlines = [
        [(float(x - minx), float(y - miny)) for (x, y) in ring] for ring in outlines
    ]

    canvas_w = max(1, int(round(box_w * PX_PER_MM)))
    canvas_h = max(1, int(round(box_h * PX_PER_MM)))
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # --- 8. Fond de couleur optionnel (limite a la forme decoupee) ------
    rgb = parse_hex_color(bg_color)
    if rgb is not None:
        cut_mask = Image.new("L", (canvas_w, canvas_h), 0)
        mask_draw = ImageDraw.Draw(cut_mask)
        for ring in local_outlines:
            points = [
                (x * PX_PER_MM, canvas_h - y * PX_PER_MM) for (x, y) in ring
            ]
            if len(points) >= 3:
                mask_draw.polygon(points, fill=255)
        color_layer = Image.new("RGBA", (canvas_w, canvas_h), (*rgb, 255))
        color_layer.putalpha(cut_mask)
        canvas.alpha_composite(color_layer)

    # Position du visuel dans le canevas (Y image vers le bas).
    paste_x = int(round(-minx * PX_PER_MM))
    paste_y = int(round((box_h - (img_h_mm - miny)) * PX_PER_MM))
    # alpha_composite = composition "source over" : le fond colore reste visible
    # sous les pixels semi-transparents du visuel (contrairement a paste+mask).
    canvas.alpha_composite(img, (paste_x, paste_y))

    return PreparedSticker(
        name=name,
        image=canvas,
        outlines_mm=local_outlines,
        width_mm=canvas_w / PX_PER_MM,
        height_mm=canvas_h / PX_PER_MM,
        rotated=False,
        uid=uid,
    )


def prepare_from_config(spec, cfg: MachineConfig) -> PreparedSticker:
    """Raccourci : prepare un StickerSpec avec les reglages courants."""
    return prepare_sticker(
        png_bytes=spec.png_bytes,
        name=spec.name,
        mode=spec.mode,
        size_mm=spec.size_mm,
        border_mm=cfg.border_mm,
        simplify_mm=cfg.simplify_mm,
        corner_style=cfg.corner_style,
        bg_color=resolve_bg_color(spec.bg_mode, spec.bg_color, cfg),
        uid=spec.uid,
    )

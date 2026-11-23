"""Placement 2D multi-planches (algorithme MaxRects / Best-Short-Side-Fit).

Chaque sticker est place dans une "boite" agrandie de ``SPACING_MM`` : ainsi
deux contours de decoupe ne peuvent jamais se toucher, et la rotation a 90 deg
est autorisee si elle fait gagner de la place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .models import MachineConfig, PreparedSticker

EPS = 1e-6
MAX_SHEETS = 80  # garde-fou anti-boucle infinie


class PackingError(ValueError):
    """Placement impossible (message directement affichable)."""


@dataclass(eq=False)
class Placement:
    """Un sticker pose sur une planche (x, y = coin bas-gauche de sa boite)."""

    sticker: PreparedSticker
    x_mm: float
    y_mm: float

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (
            self.x_mm,
            self.y_mm,
            self.x_mm + self.sticker.width_mm,
            self.y_mm + self.sticker.height_mm,
        )


@dataclass(eq=False)
class Sheet:
    """Une planche physique (une feuille)."""

    index: int
    placements: list[Placement] = field(default_factory=list)

    @property
    def sticker_count(self) -> int:
        return len(self.placements)

    @property
    def contour_count(self) -> int:
        return sum(len(p.sticker.outlines_mm) for p in self.placements)

    def utilization(self, cfg: MachineConfig) -> float:
        used = sum(
            p.sticker.width_mm * p.sticker.height_mm for p in self.placements
        )
        plate = cfg.plate_w_mm * cfg.plate_h_mm
        return used / plate if plate > 0 else 0.0

    def bounds(self) -> tuple[float, float, float, float] | None:
        if not self.placements:
            return None
        boxes = [p.bbox for p in self.placements]
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )


def _contains(outer, inner) -> bool:
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (
        ix >= ox - EPS
        and iy >= oy - EPS
        and ix + iw <= ox + ow + EPS
        and iy + ih <= oy + oh + EPS
    )


def _prune(rects: list[tuple[float, float, float, float]]):
    """Supprime les rectangles entierement inclus dans un autre."""
    if len(rects) > 2500:
        rects = sorted(rects, key=lambda r: r[2] * r[3], reverse=True)[:2500]
    kept = []
    for i, rect in enumerate(rects):
        if any(
            j != i and rects[j] != rect and _contains(rects[j], rect)
            for j in range(len(rects))
        ):
            continue
        kept.append(rect)
    return kept


class MaxRectsBin:
    """Un plateau : ensemble de rectangles libres, decoupes a chaque pose."""

    def __init__(self, width: float, height: float):
        self.width = float(width)
        self.height = float(height)
        self.free: list[tuple[float, float, float, float]] = [
            (0.0, 0.0, self.width, self.height)
        ]

    def insert(
        self, width: float, height: float, allow_rotation: bool = True
    ) -> tuple[float, float, bool] | None:
        """Pose la boite (w, h). Retourne (x, y, tourne_90) ou None."""
        best_score = None
        best: tuple[float, float, float, float, bool] | None = None

        for rx, ry, rw, rh in self.free:
            # Orientation normale.
            if width <= rw + EPS and height <= rh + EPS:
                score = (
                    min(rw - width, rh - height),
                    max(rw - width, rh - height),
                    0,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best = (rx, ry, width, height, False)
            # Orientation tournee a 90 deg.
            if (
                allow_rotation
                and abs(width - height) > EPS
                and height <= rw + EPS
                and width <= rh + EPS
            ):
                score = (
                    min(rw - height, rh - width),
                    max(rw - height, rh - width),
                    1,
                )
                if best_score is None or score < best_score:
                    best_score = score
                    best = (rx, ry, height, width, True)

        if best is None:
            return None

        x, y, box_w, box_h, rotated = best
        self._split(x, y, box_w, box_h)
        return x, y, rotated

    def _split(self, x: float, y: float, w: float, h: float) -> None:
        new_rects = []
        for rx, ry, rw, rh in self.free:
            # Pas de chevauchement : on garde le rectangle tel quel.
            if (
                x >= rx + rw - EPS
                or x + w <= rx + EPS
                or y >= ry + rh - EPS
                or y + h <= ry + EPS
            ):
                new_rects.append((rx, ry, rw, rh))
                continue
            # Decoupe en (jusqu'a) 4 morceaux libres autour de la boite posee.
            if x > rx + EPS:
                new_rects.append((rx, ry, x - rx, rh))
            if x + w < rx + rw - EPS:
                new_rects.append((x + w, ry, rx + rw - (x + w), rh))
            if y > ry + EPS:
                new_rects.append((rx, ry, rw, y - ry))
            if y + h < ry + rh - EPS:
                new_rects.append((rx, y + h, rw, ry + rh - (y + h)))
        self.free = _prune(new_rects)


def _fits(width: float, height: float, usable_w: float, usable_h: float) -> bool:
    return width <= usable_w + EPS and height <= usable_h + EPS


def _clamp_center(value: float, start: float, span: float, size: float) -> float:
    """Ramene un centre pour que la boite (taille ``size``) reste dans la zone."""
    if size >= span:
        return start + span / 2.0
    return min(max(value, start + size / 2.0), start + span - size / 2.0)


def sheets_from_layout(
    layout: Sequence[dict],
    prepared_by_uid: dict[str, PreparedSticker],
    cfg: MachineConfig,
) -> list[Sheet]:
    """Construit les planches a partir de positions manuelles.

    ``layout`` est une liste de planches, chacune contenant ``placements`` :
    ``{"uid": str, "cx": float, "cy": float, "rotated": bool}`` (centre en mm
    dans le repere bas-gauche). Les stickers qui depasseraient la zone utile
    sont ramenes a l'interieur ; aucun espacement n'est impose.
    """
    x0 = cfg.margin_mm
    y0 = cfg.margin_mm
    usable_w = cfg.usable_w_mm
    usable_h = cfg.usable_h_mm

    rotated_cache: dict[str, PreparedSticker] = {}
    sheets: list[Sheet] = []
    for entry in layout or []:
        placements: list[Placement] = []
        for item in entry.get("placements") or []:
            uid = str(item.get("uid") or "")
            base = prepared_by_uid.get(uid)
            if base is None:
                continue
            sticker = base
            if item.get("rotated"):
                if uid not in rotated_cache:
                    rotated_cache[uid] = base.rotated_ccw()
                sticker = rotated_cache[uid]
            width = sticker.width_mm
            height = sticker.height_mm
            try:
                cx = float(item.get("cx") or 0.0)
                cy = float(item.get("cy") or 0.0)
            except (TypeError, ValueError):
                continue
            cx = _clamp_center(cx, x0, usable_w, width)
            cy = _clamp_center(cy, y0, usable_h, height)
            placements.append(
                Placement(
                    sticker=sticker,
                    x_mm=cx - width / 2.0,
                    y_mm=cy - height / 2.0,
                )
            )
        if placements:
            sheets.append(Sheet(index=len(sheets) + 1, placements=placements))
    return sheets


def layout_matches(layout: Sequence[dict] | None, expected: dict[str, int]) -> bool:
    """La disposition manuelle couvre-t-elle exactement les stickers attendus ?"""
    if not layout:
        return False
    counts: dict[str, int] = {}
    for entry in layout:
        for item in entry.get("placements") or []:
            uid = str(item.get("uid") or "")
            counts[uid] = counts.get(uid, 0) + 1
    return counts == {uid: int(n) for uid, n in expected.items() if int(n) > 0}


def overlapping_pairs(sheet: Sheet, tolerance_mm2: float = 1.0) -> list[tuple[int, int]]:
    """Paires de stickers dont les tracés de découpe se chevauchent vraiment.

    Les boîtes englobantes servent de pré-filtre rapide ; l'intersection réelle
    des contours est ensuite calculée (Shapely) pour ne pas signaler deux
    silhouettes qui ne se touchent pas.
    """
    from shapely.affinity import translate
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    def shape_of(placement: Placement):
        polygons = []
        for outline in placement.sticker.outlines_mm:
            if len(outline) < 3:
                continue
            try:
                polygon = Polygon(outline)
            except Exception:  # pragma: no cover - contour degenere
                continue
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if not polygon.is_empty:
                polygons.append(polygon)
        if not polygons:
            return None
        return translate(
            unary_union(polygons), placement.x_mm, placement.y_mm
        )

    placements = sheet.placements
    shapes = [shape_of(p) for p in placements]
    pairs: list[tuple[int, int]] = []
    for i in range(len(placements)):
        ax0, ay0, ax1, ay1 = placements[i].bbox
        for j in range(i + 1, len(placements)):
            bx0, by0, bx1, by1 = placements[j].bbox
            overlap_w = min(ax1, bx1) - max(ax0, bx0)
            overlap_h = min(ay1, by1) - max(ay0, by0)
            if overlap_w <= 0 or overlap_h <= 0:
                continue
            if overlap_w * overlap_h <= tolerance_mm2:
                continue
            first, second = shapes[i], shapes[j]
            if first is None or second is None:
                pairs.append((i, j))
                continue
            if first.intersection(second).area > tolerance_mm2:
                pairs.append((i, j))
    return pairs


def pack(units: Sequence[PreparedSticker], cfg: MachineConfig) -> list[Sheet]:
    """Repartit les stickers sur une ou plusieurs planches.

    ``units`` contient un element par sticker physique (la quantite est deja
    developpee). Le tri par aire decroissante ameliore le remplissage.
    """
    if not units:
        raise PackingError("Aucun sticker a placer.")

    usable_w = cfg.usable_w_mm
    usable_h = cfg.usable_h_mm
    spacing = max(0.0, cfg.spacing_mm)

    # Verification rapide : un sticker trop grand doit etre signale clairement.
    for sticker in units:
        fits_normal = _fits(
            sticker.width_mm + spacing, sticker.height_mm + spacing, usable_w, usable_h
        )
        fits_rot = cfg.allow_rotation and _fits(
            sticker.height_mm + spacing, sticker.width_mm + spacing, usable_w, usable_h
        )
        if not (fits_normal or fits_rot):
            raise PackingError(
                f"« {sticker.name} » ({sticker.width_mm:.1f} x "
                f"{sticker.height_mm:.1f} mm, bordure comprise) ne tient pas "
                f"dans la zone utile de {usable_w:.1f} x {usable_h:.1f} mm.\n\n"
                "Reduisez la dimension cible dans la liste, ou diminuez "
                "l'epaisseur de bordure / la marge exterieure."
            )

    # Les objets identiques partagent la meme image tournee (economie memoire).
    rotated_cache: dict[int, PreparedSticker] = {}

    def rotated(sticker: PreparedSticker) -> PreparedSticker:
        key = id(sticker)
        if key not in rotated_cache:
            rotated_cache[key] = sticker.rotated_ccw()
        return rotated_cache[key]

    pending = sorted(
        units,
        key=lambda s: (s.width_mm * s.height_mm, max(s.width_mm, s.height_mm)),
        reverse=True,
    )

    sheets: list[Sheet] = []
    while pending:
        if len(sheets) >= MAX_SHEETS:
            raise PackingError(
                f"Plus de {MAX_SHEETS} planches necessaires : verifiez les quantites."
            )

        bin_ = MaxRectsBin(usable_w, usable_h)
        placements: list[Placement] = []
        remaining = list(pending)

        # On remplit la planche tant qu'au moins un sticker restant y entre.
        while True:
            placed_something = False
            for sticker in list(remaining):
                result = bin_.insert(
                    sticker.width_mm + spacing,
                    sticker.height_mm + spacing,
                    allow_rotation=cfg.allow_rotation
                    and abs(sticker.width_mm - sticker.height_mm) > EPS,
                )
                if result is None:
                    continue
                x, y, is_rotated = result
                placed = rotated(sticker) if is_rotated else sticker
                placements.append(
                    Placement(
                        sticker=placed,
                        x_mm=cfg.margin_mm + x + spacing / 2.0,
                        y_mm=cfg.margin_mm + y + spacing / 2.0,
                    )
                )
                remaining.remove(sticker)
                placed_something = True

            if not placed_something:
                break

        if not placements:  # securite : ne devrait jamais arriver
            raise PackingError(
                "Aucun sticker n'a pu etre place : verifiez les dimensions."
            )

        sheets.append(Sheet(index=len(sheets) + 1, placements=placements))
        pending = remaining

    return sheets

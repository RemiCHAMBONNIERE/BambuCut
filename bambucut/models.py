"""Modeles de donnees partages par toute l'application.

Aucune dependance a Streamlit ici : ces objets sont utilises aussi bien par
l'interface que par les tests automatiques.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from typing import Sequence

from PIL import Image

# Un point en millimetres, repere bas-gauche (0, 0).
Point = tuple[float, float]

# Styles d'angles pour le buffer de bordure.
CORNER_ROUND = "round"
CORNER_SHARP = "sharp"
CORNER_STYLES = (CORNER_ROUND, CORNER_SHARP)

# Contour (fond de couleur) de chaque sticker.
BG_INHERIT = "inherit"  # suit le reglage global de la barre laterale
BG_CUSTOM = "custom"    # couleur propre au sticker
BG_NONE = "none"        # pas de fond : bordure papier / blanche
BG_MODES = (BG_INHERIT, BG_CUSTOM, BG_NONE)

# Champs sauvegardes dans config.json (dans cet ordre).
CONFIG_FIELDS = (
    "plate_w_mm",
    "plate_h_mm",
    "margin_mm",
    "spacing_mm",
    "border_mm",
    "simplify_mm",
    "corner_style",
    "allow_rotation",
    "bg_enabled",
    "bg_color",
    "show_dimensions",
    "show_scale",
    "calib_x_mm",
    "calib_y_mm",
    "offset_x_mm",
    "offset_y_mm",
    "z_cut_mm",
    "z_travel_mm",
    "feed_cut",
    "feed_travel",
    "plunge_feed",
    "home_xy",
)


@dataclass(frozen=True)
class MachineConfig:
    """Tous les reglages machine / plateau / bordures."""

    # --- Plateau et placement ---
    plate_w_mm: float = 180.0
    plate_h_mm: float = 180.0
    margin_mm: float = 10.0
    spacing_mm: float = 3.0

    # --- Rendu des stickers ---
    border_mm: float = 2.5
    simplify_mm: float = 0.25
    corner_style: str = CORNER_ROUND
    allow_rotation: bool = True

    # --- Fond de couleur & annotations d'apercu ---
    bg_enabled: bool = False
    bg_color: str = "#FFE0B2"
    show_dimensions: bool = True
    show_scale: bool = True

    # --- Calibrage Bambu Lab A1 mini ---
    calib_x_mm: float = 10.0
    calib_y_mm: float = 10.0
    offset_x_mm: float = 0.0
    offset_y_mm: float = 0.0

    # --- Axe Z et vitesses ---
    z_cut_mm: float = 14.2
    z_travel_mm: float = 18.2
    feed_cut: int = 1200
    feed_travel: int = 3000
    plunge_feed: int = 600

    # --- Depart du programme ---
    home_xy: bool = False

    # ------------------------------------------------------------------
    # Proprietes derivees
    # ------------------------------------------------------------------
    @property
    def usable_w_mm(self) -> float:
        """Largeur reellement utilisable (plateau moins les marges)."""
        return self.plate_w_mm - 2.0 * self.margin_mm

    @property
    def usable_h_mm(self) -> float:
        """Hauteur reellement utilisable (plateau moins les marges)."""
        return self.plate_h_mm - 2.0 * self.margin_mm

    def as_dict(self) -> dict:
        """Representation serialisable (config.json, ZIP, signature...)."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def problems(self) -> list[str]:
        """Controles de coherence. Retourne une liste de messages (vide = OK)."""
        problems: list[str] = []
        if self.plate_w_mm < 20 or self.plate_h_mm < 20:
            problems.append("Le plateau doit mesurer au moins 20 mm de cote.")
        if self.usable_w_mm < 20 or self.usable_h_mm < 20:
            problems.append(
                "La zone utile est trop petite : reduisez la marge exterieure."
            )
        if self.border_mm < 0:
            problems.append("L'epaisseur de bordure ne peut pas etre negative.")
        if self.spacing_mm < 0:
            problems.append("L'espacement ne peut pas etre negatif.")
        if self.z_cut_mm <= 0:
            problems.append("La hauteur Z_CUT doit etre positive.")
        if self.z_travel_mm <= self.z_cut_mm:
            problems.append("Z_TRAVEL doit etre superieur a Z_CUT (la lame doit lever).")
        if min(self.feed_cut, self.feed_travel, self.plunge_feed) <= 0:
            problems.append("Les vitesses doivent etre positives.")
        if self.corner_style not in CORNER_STYLES:
            problems.append("Style d'angle inconnu.")
        return problems


@dataclass(eq=False)
class StickerSpec:
    """Une image importee par l'utilisateur, avant traitement."""

    uid: str
    name: str
    png_bytes: bytes
    width_px: int
    height_px: int
    mode: str = "width"  # "width" ou "height"
    size_mm: float = 45.0
    qty: int = 1
    bg_mode: str = BG_INHERIT
    bg_color: str = "#FFE0B2"

    @property
    def aspect(self) -> float:
        """Largeur / hauteur de l'image source (toujours > 0)."""
        if self.height_px <= 0:
            return 1.0
        return self.width_px / self.height_px


@dataclass(eq=False)
class PreparedSticker:
    """Sticker pret a etre place : image + contours de decoupe, en mm.

    ``image`` couvre exactement la boite englobante des contours de coupe
    (fond transparent autour du visuel) et ``outlines_mm`` est exprime dans le
    repere local de cette image (origine = coin bas-gauche, Y vers le haut).
    """

    name: str
    image: Image.Image
    outlines_mm: list[list[Point]]
    width_mm: float
    height_mm: float
    rotated: bool = False
    uid: str = ""

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    @property
    def points_count(self) -> int:
        return sum(len(p) for p in self.outlines_mm)

    def rotated_ccw(self) -> "PreparedSticker":
        """Rotation de 90 degres (sens anti-horaire) de l'image ET des contours."""
        old_h = self.height_mm
        outlines = [[(old_h - y, x) for (x, y) in poly] for poly in self.outlines_mm]
        return PreparedSticker(
            name=self.name,
            image=self.image.transpose(Image.Transpose.ROTATE_90),
            outlines_mm=outlines,
            width_mm=self.height_mm,
            height_mm=self.width_mm,
            rotated=not self.rotated,
            uid=self.uid,
        )


def target_size_mm(aspect: float, mode: str, size_mm: float) -> tuple[float, float]:
    """Calcule la taille (largeur, hauteur) en mm en conservant strictement le ratio."""
    aspect = max(aspect, 1e-6)
    if mode == "height":
        return size_mm * aspect, size_mm
    return size_mm, size_mm / aspect


def other_dimension_mm(aspect: float, mode: str, size_mm: float) -> float:
    """Dimension non pilotee (info affichee dans l'interface)."""
    w, h = target_size_mm(aspect, mode, size_mm)
    return h if mode == "width" else w


def polyline_length_mm(points: Sequence[Point]) -> float:
    """Longueur d'une polyligne (non fermee)."""
    return sum(
        math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)
    )


def parse_hex_color(value: str | None) -> tuple[int, int, int] | None:
    """Convertit '#RRGGBB' (ou '#RGB') en (r, g, b), ou None si invalide."""
    if not value:
        return None
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return None


def resolve_bg_color(
    bg_mode: str, bg_color: str | None, cfg: MachineConfig
) -> str | None:
    """Couleur de contour effective d'un sticker (None = bordure papier).

    ``BG_INHERIT`` suit ``bg_enabled`` / ``bg_color`` de la configuration,
    ``BG_CUSTOM`` force ``bg_color`` et ``BG_NONE`` desactive le fond.
    """
    if bg_mode == BG_NONE:
        return None
    if bg_mode == BG_CUSTOM:
        return bg_color if parse_hex_color(bg_color) else cfg.bg_color
    return cfg.bg_color if cfg.bg_enabled else None


def scaled_size_mm(
    base_size_mm: float,
    scale: float,
    max_dim_mm: float,
    min_size_mm: float = 5.0,
    extra_mm: float = 0.0,
) -> float:
    """Nouvelle dimension cible apres un redimensionnement proportionnel.

    ``scale`` vient de l'editeur d'apercu (1.0 = taille d'origine). Le resultat
    est arrondi au dixieme et borne pour rester saisissable dans la liste.

    ``extra_mm`` est une marge fixe autour du visuel (typiquement deux fois
    l'epaisseur de bordure) : elle est agrandie avec le reste afin que la boite
    finale corresponde exactement a la taille affichee dans l'editeur.
    """
    try:
        value = (float(base_size_mm) + float(extra_mm)) * float(scale) - float(
            extra_mm
        )
    except (TypeError, ValueError):
        return float(base_size_mm)
    if value != value:  # NaN
        return float(base_size_mm)
    value = round(value, 1)
    return max(float(min_size_mm), min(float(max_dim_mm), value))

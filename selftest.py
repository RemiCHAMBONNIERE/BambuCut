"""Autotest BambuCut (sans Streamlit).

Genere quelques images de synthese, execute toute la chaine (geometrie,
placement, PDF, G-code, apercu) et verifie les invariants importants :

    .venv\\Scripts\\python.exe selftest.py

Les fichiers produits sont ecrits dans ``_selftest_out/`` pour inspection.
"""

from __future__ import annotations

import base64
import json
import math
import re
import shutil
import sys
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from bambucut.gcode import build_gcode, check_safety, cut_length_mm, out_of_bounds
from bambucut.geometry import PX_PER_MM, prepare_sticker
from bambucut.models import MachineConfig, PreparedSticker, StickerSpec
from bambucut.packing import pack
from bambucut.pdf_export import build_pdf
from bambucut.intro import COMPONENT_DIR as INTRO_DIR
from bambucut.intro import (
    DEFAULT_INTRO_TEXTS,
    INTRO_PAGE_CSS,
    load_intro_texts,
)
from bambucut.preview import render_preview
from bambucut.theme import (
    DEFAULT_RECIPIENT,
    STYLE_GIFT,
    STYLE_SOBER,
    hero_html,
    load_ui_prefs,
    save_ui_prefs,
    theme_css,
    zip_readme,
)

OUT = Path(__file__).resolve().parent / "_selftest_out"
FAILURES: list[str] = []


def check(condition: bool, message: str) -> None:
    if condition:
        print(f"  [ok] {message}")
    else:
        print(f"  [ECHEC] {message}")
        FAILURES.append(message)


# ---------------------------------------------------------------------------
# Images de synthese
# ---------------------------------------------------------------------------
def png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_blob() -> bytes:
    """Forme orange avec un trou central + un petit point detache."""
    image = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([30, 30, 570, 370], radius=70, fill=(240, 120, 40, 255))
    draw.ellipse([230, 130, 370, 270], fill=(0, 0, 0, 0))  # trou
    draw.ellipse([470, 300, 545, 375], fill=(40, 90, 220, 255))  # piece detachee
    return png_bytes(image)


def make_star() -> bytes:
    """Etoile verticale (ratio tres allonge)."""
    image = Image.new("RGBA", (300, 900), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    cx, cy, outer, inner = 150, 450, 140, 55
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else inner
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=(30, 160, 110, 255))
    return png_bytes(image)


def make_opaque() -> bytes:
    """Image RGB sans canal alpha (doit donner un rectangle)."""
    image = Image.new("RGB", (400, 300), (250, 230, 60))
    draw = ImageDraw.Draw(image)
    draw.ellipse([40, 40, 360, 260], fill=(230, 60, 90))
    return png_bytes(image)


def make_transparent() -> bytes:
    return png_bytes(Image.new("RGBA", (100, 100), (0, 0, 0, 0)))


# ---------------------------------------------------------------------------
# Outils de verification
# ---------------------------------------------------------------------------
def rasterize(sticker, scale: float = PX_PER_MM) -> np.ndarray:
    """Rasterise les contours d'un PreparedSticker a sa resolution."""
    w = max(1, int(round(sticker.width_mm * scale)))
    h = max(1, int(round(sticker.height_mm * scale)))
    image = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(image)
    for poly in sticker.outlines_mm:
        points = [(x * scale, h - y * scale) for (x, y) in poly]
        if len(points) >= 3:
            draw.polygon(points, fill=255)
    return np.array(image) > 0


def fill_holes(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(
        mask.astype(np.uint8) * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
    )
    filled = np.zeros_like(mask, dtype=np.uint8)
    if contours:
        cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled > 0


def assert_geometry(sticker, border_mm: float, label: str, check_border: bool = True) -> None:
    art = np.array(sticker.image.getchannel("A")) > 127
    poly = rasterize(sticker)
    check(art.shape == poly.shape, f"{label} : dimensions image/contours coherentes")
    check(art.any(), f"{label} : visuel non vide")

    # Tout le visuel doit etre a l'interieur du trace de coupe.
    poly_dilated = cv2.dilate(poly.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    outside = int((art & ~poly_dilated).sum())
    check(outside == 0, f"{label} : visuel entierement dans la decoupe ({outside} px dehors)")

    if not check_border:
        return

    # Le trace doit correspondre a la silhouette + bordure (silhouette trouee
    # remplie, comme le fait le pipeline de decoupe).
    expected = fill_holes(art)
    radius_px = max(1, int(round(border_mm * PX_PER_MM)))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (2 * radius_px + 1, 2 * radius_px + 1)
    )
    expected_dilated = cv2.dilate(expected.astype(np.uint8), kernel) > 0
    ratio = poly.sum() / max(1, expected_dilated.sum())
    check(
        0.85 <= ratio <= 1.05,
        f"{label} : aire de coupe / silhouette+bordure = {ratio:.3f}",
    )
    check(
        poly.sum() > expected.sum(),
        f"{label} : la bordure ajoute bien de la matiere",
    )


# ---------------------------------------------------------------------------
# Scenario complet
# ---------------------------------------------------------------------------
def main() -> int:
    print("BambuCut - autotest")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    cfg = MachineConfig()
    check(cfg.usable_w_mm == 160.0, "zone utile par defaut = 160 x 160 mm")

    specs = [
        StickerSpec("blob", "blob.png", make_blob(), 600, 400, "width", 45.0, 3),
        StickerSpec("star", "star.png", make_star(), 300, 900, "height", 60.0, 4),
        StickerSpec("opaque", "opaque.png", make_opaque(), 400, 300, "width", 40.0, 2),
    ]

    # Conserve les images d'entree pour inspection / tests d'interface.
    inputs_dir = OUT / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        (inputs_dir / spec.name).write_bytes(spec.png_bytes)

    print("\n[1] Traitement d'image")
    prepared = {}
    for spec in specs:
        sticker = prepare_sticker(
            spec.png_bytes,
            spec.name,
            spec.mode,
            spec.size_mm,
            cfg.border_mm,
            cfg.simplify_mm,
            cfg.corner_style,
            uid=spec.uid,
        )
        prepared[spec.uid] = sticker
        print(
            f"  - {spec.name}: {sticker.width_mm:.2f} x {sticker.height_mm:.2f} mm, "
            f"{len(sticker.outlines_mm)} contour(s), {sticker.points_count} points"
        )
        assert_geometry(
            sticker, cfg.border_mm, spec.name, check_border=(spec.uid != "opaque")
        )
        assert abs(sticker.width_mm) < 200 and abs(sticker.height_mm) < 200

        rotated = sticker.rotated_ccw()
        check(
            abs(rotated.width_mm - sticker.height_mm) < 1e-6
            and abs(rotated.height_mm - sticker.width_mm) < 1e-6,
            f"{spec.name} : rotation 90° echange largeur/hauteur",
        )
        assert_geometry(
            rotated,
            cfg.border_mm,
            f"{spec.name} tourne",
            check_border=(spec.uid != "opaque"),
        )

    # Cas d'erreur : PNG entierement transparent.
    try:
        prepare_sticker(make_transparent(), "vide.png", "width", 20, 2.5, 0.25)
    except ValueError:
        check(True, "image entierement transparente correctement refusee")
    else:
        check(False, "image entierement transparente devrait lever une erreur")

    # Rectangle sans alpha : bbox = dimensions demandees + 2 x bordure.
    rect = prepared["opaque"]
    check(
        abs(rect.width_mm - (40.0 + 2 * cfg.border_mm)) < 0.15,
        f"image sans alpha -> rectangle ({rect.width_mm:.2f} mm de large)",
    )

    print("\n[1 bis] Fond de couleur")
    colored = prepare_sticker(
        specs[0].png_bytes,
        "blob-fond.png",
        "width",
        45.0,
        cfg.border_mm,
        cfg.simplify_mm,
        cfg.corner_style,
        bg_color="#FF0000",
    )
    check(
        colored.image.size == prepared["blob"].image.size,
        "fond : meme canevas que le sticker d'origine",
    )
    base_alpha = np.array(prepared["blob"].image.getchannel("A"))
    colored_rgba = np.array(colored.image)
    cut = rasterize(prepared["blob"])
    open_inside = (base_alpha == 0) & cut
    check(bool(open_inside.any()), "fond : zone transparente a l'interieur de la coupe")
    ys, xs = np.nonzero(open_inside)
    sample_y = int(ys[len(ys) // 2])
    sample_x = int(xs[len(xs) // 2])
    pixel = colored_rgba[sample_y, sample_x]
    check(
        int(pixel[3]) == 255 and int(pixel[0]) > 200 and int(pixel[1]) < 60,
        f"fond rouge applique dans la zone transparente {tuple(int(v) for v in pixel)}",
    )
    check(int(colored_rgba[2, 2, 3]) == 0, "fond : rien en dehors du trace de decoupe")
    check(
        int((cut & (colored_rgba[..., 3] < 250)).sum()) == 0,
        "fond : toute la forme decoupee est opaque",
    )

    print("\n[1 ter] Configuration")
    from bambucut.config import sanitize

    cfg_test = sanitize(
        {"bg_color": "#abc", "bg_enabled": True, "show_dimensions": False}
    )
    check(
        cfg_test["bg_color"] == "#AABBCC"
        and cfg_test["bg_enabled"] is True
        and cfg_test["show_dimensions"] is False,
        "config : couleur normalisee et nouvelles options sauvegardees",
    )

    print("\n[1 quater] Contour par sticker")
    from bambucut.models import (
        BG_CUSTOM,
        BG_INHERIT,
        BG_NONE,
        resolve_bg_color,
        scaled_size_mm,
    )

    check(
        resolve_bg_color(BG_INHERIT, "#112233", MachineConfig()) is None,
        "contour : 'global' suit un fond global desactive",
    )
    check(
        resolve_bg_color(
            BG_INHERIT, "#112233", MachineConfig(bg_enabled=True, bg_color="#00FF00")
        )
        == "#00FF00",
        "contour : 'global' suit la couleur globale activee",
    )
    check(
        resolve_bg_color(BG_CUSTOM, "#123456", MachineConfig()) == "#123456",
        "contour : couleur propre au sticker prioritaire",
    )
    check(
        resolve_bg_color(BG_NONE, "#123456", MachineConfig(bg_enabled=True)) is None,
        "contour : 'sans fond' ignore la couleur globale",
    )
    check(
        resolve_bg_color(BG_CUSTOM, "n'importe quoi", cfg) == cfg.bg_color,
        "contour : couleur invalide -> repli sur la couleur globale",
    )
    check(
        prepared["blob"].uid == "blob" and prepared["blob"].rotated_ccw().uid == "blob",
        "uid du sticker conserve apres rotation",
    )

    blue = prepare_sticker(
        specs[0].png_bytes,
        "blob-fond-bleu.png",
        "width",
        45.0,
        cfg.border_mm,
        cfg.simplify_mm,
        cfg.corner_style,
        bg_color="#0000FF",
        uid="blob",
    )
    blue_pixel = np.array(blue.image)[sample_y, sample_x]
    check(
        int(blue_pixel[2]) > 200 and int(blue_pixel[0]) < 60 and int(blue_pixel[3]) == 255,
        f"contour : chaque sticker peut avoir sa couleur {tuple(int(v) for v in blue_pixel)}",
    )

    check(
        scaled_size_mm(45.0, 1.3, 180.0) == 58.5
        and scaled_size_mm(45.0, 10.0, 180.0) == 180.0
        and scaled_size_mm(45.0, 0.001, 180.0) == 5.0,
        "editeur : echelle -> dimension bornee (5 mm .. plateau)",
    )
    check(
        scaled_size_mm(45.0, 2.5, 180.0, extra_mm=5.0) == 120.0,
        "editeur : la bordure fixe est compensee (boite = 125 mm apres agrandissement)",
    )

    print("\n[2] Placement multi-planches")
    units = []
    for spec in specs:
        units.extend([prepared[spec.uid]] * spec.qty)
    sheets = pack(units, cfg)
    check(len(sheets) >= 1, f"{len(units)} stickers repartis sur {len(sheets)} planche(s)")
    check(
        sum(s.sticker_count for s in sheets) == len(units),
        "tous les stickers sont places exactement une fois",
    )
    spacing = cfg.spacing_mm
    for sheet in sheets:
        for i, placement in enumerate(sheet.placements):
            x0, y0, x1, y1 = placement.bbox
            check(
                x0 >= cfg.margin_mm - 1e-6
                and y0 >= cfg.margin_mm - 1e-6
                and x1 <= cfg.plate_w_mm - cfg.margin_mm + 1e-6
                and y1 <= cfg.plate_h_mm - cfg.margin_mm + 1e-6,
                f"planche {sheet.index} sticker {i + 1} dans la zone utile",
            )
            for j in range(i + 1, len(sheet.placements)):
                other = sheet.placements[j]
                ox0, oy0, ox1, oy1 = other.bbox
                separation_x = max(ox0 - x1, x0 - ox1)
                separation_y = max(oy0 - y1, y0 - oy1)
                check(
                    max(separation_x, separation_y) >= spacing - 1e-6,
                    f"planche {sheet.index} : espacement >= {spacing} mm entre {i + 1} et {j + 1}",
                )

    # Un sticker trop grand doit etre refuse avec un message clair.
    try:
        pack([PreparedSticker("trop-grand", prepared["blob"].image, prepared["blob"].outlines_mm, 200, 200)], cfg)
    except ValueError as exc:
        check("ne tient pas" in str(exc), "sticker trop grand refuse avec un message explicite")
    else:
        check(False, "un sticker trop grand doit lever une erreur")

    print("\n[2 bis] Editeur d'apercu")
    from bambucut.editor import (
        COMPONENT_DIR,
        editor_items,
        thumbnail_data_url,
    )

    thumbs = {uid: thumbnail_data_url(sticker.image) for uid, sticker in prepared.items()}
    check(
        all(value.startswith("data:image/png;base64,") for value in thumbs.values()),
        "editeur : vignettes PNG encodees en data URL",
    )
    thumb = Image.open(
        BytesIO(base64.b64decode(thumbs["blob"].split(",", 1)[1]))
    )
    check(max(thumb.size) <= 200, f"editeur : vignette legere ({thumb.size[0]}x{thumb.size[1]} px)")

    payload = [
        {
            "uid": placement.sticker.uid,
            "name": placement.sticker.name,
            "x": placement.x_mm,
            "y": placement.y_mm,
            "w": placement.sticker.width_mm,
            "h": placement.sticker.height_mm,
        }
        for placement in sheets[0].placements
    ]
    items = editor_items(payload, thumbs)
    base_sizes = {spec.uid: spec.size_mm for spec in specs}
    check(
        len(items) == sheets[0].sticker_count
        and all(item["uid"] in base_sizes for item in items),
        "editeur : un item par sticker pose, rattache a un sticker importe",
    )
    check(
        [item["id"] for item in items] == [f"1:{i}" for i in range(len(items))],
        "editeur : identifiants de placement uniques par planche",
    )
    check(
        all(item["img"].startswith("data:image/png") for item in items),
        "editeur : chaque item porte son image",
    )
    check(
        all(
            0 <= item["x"] and 0 <= item["y"]
            and item["x"] + item["w"] <= cfg.plate_w_mm + 1e-6
            and item["y"] + item["h"] <= cfg.plate_h_mm + 1e-6
            for item in items
        ),
        "editeur : positions dans le plateau (mm, coin bas-gauche)",
    )

    # Redimensionnement : echelle 1.3 -> nouvelle dimension cible, ratio conserve.
    new_size = scaled_size_mm(base_sizes["blob"], 1.3, cfg.plate_w_mm)
    bigger = prepare_sticker(
        specs[0].png_bytes,
        "blob.png",
        "width",
        new_size,
        cfg.border_mm,
        cfg.simplify_mm,
        cfg.corner_style,
        uid="blob",
    )
    check(
        abs(new_size - 58.5) < 1e-9 and bigger.width_mm > prepared["blob"].width_mm,
        f"editeur : agrandir 45 -> {new_size} mm agrandit la decoupe",
    )
    check(
        abs((bigger.width_mm - prepared["blob"].width_mm) - (new_size - 45.0)) < 0.2,
        "editeur : la decoupe grandit exactement de la meme quantite que le visuel",
    )

    html = (COMPONENT_DIR / "index.html").read_text(encoding="utf-8")
    check(
        "streamlit:setComponentValue" in html
        and "streamlit:componentReady" in html
        and COMPONENT_DIR.exists(),
        "editeur : composant local present et protocolaire",
    )
    check(
        "startMove" in html and "pos.set" in html and "positions" in html,
        "editeur : deplacement des stickers cable dans le composant",
    )

    print("\n[2 ter] Disposition manuelle")
    from bambucut.packing import layout_matches, overlapping_pairs, sheets_from_layout

    expected: dict[str, int] = {}
    for spec in specs:
        expected[spec.uid] = expected.get(spec.uid, 0) + spec.qty

    manual_layout = []
    for sheet in sheets:
        entries = []
        for placement in sheet.placements:
            entries.append(
                {
                    "uid": placement.sticker.uid,
                    "cx": placement.x_mm + placement.sticker.width_mm / 2.0,
                    "cy": placement.y_mm + placement.sticker.height_mm / 2.0,
                    "rotated": placement.sticker.rotated,
                }
            )
        manual_layout.append({"index": sheet.index, "placements": entries})

    check(
        layout_matches(manual_layout, expected),
        "disposition : la sortie du placement automatique est reutilisable",
    )
    check(
        not layout_matches(manual_layout[:-1], expected)
        and not layout_matches(None, expected),
        "disposition : une liste incomplete ou absente est refusee",
    )

    round_trip = sheets_from_layout(manual_layout, prepared, cfg)
    check(
        [s.sticker_count for s in round_trip] == [s.sticker_count for s in sheets],
        "disposition : nombre de planches et de stickers conserves",
    )
    same_positions = True
    same_rotation = True
    for before, after in zip(sheets, round_trip):
        for old, new in zip(before.placements, after.placements):
            if abs(old.x_mm - new.x_mm) > 1e-6 or abs(old.y_mm - new.y_mm) > 1e-6:
                same_positions = False
            if old.sticker.rotated != new.sticker.rotated:
                same_rotation = False
    check(same_positions, "disposition : positions restituees au micron")
    check(same_rotation, "disposition : rotations restituees")

    rotated_layout = [
        {
            "index": 1,
            "placements": [{"uid": "star", "cx": 90.0, "cy": 90.0, "rotated": True}],
        }
    ]
    rotated_sheet = sheets_from_layout(rotated_layout, prepared, cfg)[0]
    star_rotated = rotated_sheet.placements[0].sticker
    check(
        star_rotated.rotated
        and abs(star_rotated.width_mm - prepared["star"].height_mm) < 1e-6,
        "disposition : sticker tourne de 90° restitue tourne",
    )

    clamp_layout = [
        {
            "index": 1,
            "placements": [{"uid": "blob", "cx": -500.0, "cy": 900.0, "rotated": False}],
        }
    ]
    clamped = sheets_from_layout(clamp_layout, prepared, cfg)[0].placements[0]
    cx0, cy0, cx1, cy1 = clamped.bbox
    check(
        abs(cx0 - cfg.margin_mm) < 1e-6
        and abs(cy1 - (cfg.plate_h_mm - cfg.margin_mm)) < 1e-6,
        "disposition : une position hors zone est ramenee dans la zone utile",
    )

    overlap_layout = [
        {
            "index": 1,
            "placements": [
                {"uid": "blob", "cx": 90.0, "cy": 90.0, "rotated": False},
                {"uid": "blob", "cx": 92.0, "cy": 92.0, "rotated": False},
            ],
        }
    ]
    overlap_sheet = sheets_from_layout(overlap_layout, prepared, cfg)[0]
    check(
        len(overlapping_pairs(overlap_sheet)) == 1,
        "disposition : le chevauchement manuel est detecte",
    )
    check(
        not any(overlapping_pairs(sheet) for sheet in sheets),
        "placement automatique : aucun chevauchement",
    )

    print("\n[3] Fichiers de sortie")
    for sheet in sheets:
        pdf = build_pdf(sheet, cfg, len(sheets))
        gcode = build_gcode(sheet, cfg, len(sheets))
        preview = render_preview(sheet, cfg, len(sheets))
        stem = f"planche_{sheet.index}"

        (OUT / f"{stem}_impression.pdf").write_bytes(pdf)
        (OUT / f"{stem}_decoupe.gcode").write_text(gcode, encoding="utf-8")
        (OUT / f"{stem}_previsu.png").write_bytes(preview)

        check(pdf.startswith(b"%PDF"), f"{stem} : PDF valide")
        match = re.search(rb"MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", pdf)
        if match:
            width_pt = float(match.group(1))
            expected_pt = 180.0 * 72.0 / 25.4
            check(
                abs(width_pt - expected_pt) < 0.5,
                f"{stem} : page PDF a 180 mm ({width_pt:.2f} pt)",
            )
        else:
            check(False, f"{stem} : MediaBox introuvable")

        check(not check_safety(gcode), f"{stem} : aucune commande interdite")
        forbidden = ("M104", "M109", "M140", "M190", "G29")
        commands = [
            line.split(";", 1)[0].strip()
            for line in gcode.splitlines()
            if line.split(";", 1)[0].strip()
        ]
        check(
            not any(cmd.startswith(forbidden) for cmd in commands),
            f"{stem} : pas de chauffe / nivellement",
        )
        check(
            not any(re.search(r"(?:^|\s)E\d", cmd) for cmd in commands),
            f"{stem} : aucune extrusion",
        )
        check(
            commands[0] == "G21" and "G90" in commands[:3],
            f"{stem} : unites mm + coordonnees absolues",
        )
        check(commands[-1].startswith("G0 Y175"), f"{stem} : fin avec Y175")
        check(
            any(
                cmd.startswith(f"G1 Z{cfg.z_travel_mm + 20:g} ")
                for cmd in commands
            ),
            f"{stem} : remontee finale a Z_TRAVEL+20",
        )

        z_cut_lines = [c for c in commands if c.startswith(f"G1 Z{cfg.z_cut_mm:g}")]
        check(
            len(z_cut_lines) == sheet.contour_count,
            f"{stem} : une descente de lame par contour "
            f"({len(z_cut_lines)}/{sheet.contour_count})",
        )

        coords = []
        for cmd in commands:
            if cmd.startswith(("G0 ", "G1 ")):
                x = re.search(r"X(-?[\d.]+)", cmd)
                y = re.search(r"Y(-?[\d.]+)", cmd)
                if x:
                    coords.append(("X", float(x.group(1))))
                if y:
                    coords.append(("Y", float(y.group(1))))
        in_bounds = all(
            0.0 <= value <= (cfg.plate_w_mm if axis == "X" else cfg.plate_h_mm)
            for axis, value in coords
        )
        check(in_bounds, f"{stem} : toutes les coordonnees dans le plateau")
        check(not out_of_bounds(sheet, cfg), f"{stem} : aucun debordement detecte")

        image = Image.open(BytesIO(preview))
        check(
            image.size == (round(180 * 6), round(180 * 6)),
            f"{stem} : apercu PNG {image.size[0]}x{image.size[1]}",
        )
        print(
            f"  - {stem}: {sheet.sticker_count} stickers, "
            f"occupation {sheet.utilization(cfg) * 100:.1f} %, "
            f"coupe {cut_length_mm(sheet) / 1000:.2f} m"
        )

    # Verification offset : decale toutes les coordonnees de coupe.
    def all_x(program: str) -> list[float]:
        return [
            float(m.group(1))
            for m in re.finditer(r"X(-?\d+(?:\.\d+)?)", program)
        ]

    cfg_offset = MachineConfig(offset_x_mm=2.0, offset_y_mm=-1.0)
    gcode_off = build_gcode(sheets[0], cfg_offset, len(sheets))
    base_x = all_x(build_gcode(sheets[0], cfg, len(sheets)))
    shifted_x = all_x(gcode_off)
    check(
        abs(min(shifted_x) - (min(base_x) + 2.0)) < 1e-6,
        "offset X applique au G-code",
    )

    # Apercus avec / sans cotes et regle d'echelle.
    preview_with = render_preview(
        sheets[0], cfg, len(sheets), show_dimensions=True, show_scale=True
    )
    preview_without = render_preview(
        sheets[0], cfg, len(sheets), show_dimensions=False, show_scale=False
    )
    (OUT / "planche_1_previsu_cotes.png").write_bytes(preview_with)
    (OUT / "planche_1_previsu_sans_cotes.png").write_bytes(preview_without)
    check(
        Image.open(BytesIO(preview_with)).size == (round(180 * 6), round(180 * 6)),
        "apercu avec cotes : dimensions conservees",
    )
    check(preview_with != preview_without, "options cotes/echelle modifient l'apercu")

    # ------------------------------------------------------------------
    print("\n[4] Habillage (themes gift / sober)")
    prefs_dir = OUT / "_prefs"
    shutil.rmtree(prefs_dir, ignore_errors=True)
    prefs_dir.mkdir(parents=True, exist_ok=True)

    defaults = load_ui_prefs(prefs_dir)
    check(
        defaults["style"] == STYLE_GIFT
        and defaults["recipient"] == DEFAULT_RECIPIENT
        and defaults["intro_done"] is False,
        "prefs : cadeau + prenom + intro a voir quand ui_prefs.json est absent",
    )

    save_ui_prefs(prefs_dir, {"style": STYLE_SOBER, "recipient": "  Zoé  "})
    saved = load_ui_prefs(prefs_dir)
    check(
        saved
        == {
            "style": STYLE_SOBER,
            "recipient": "Zoé",
            "intro_done": False,
        },
        "prefs : aller-retour style + prenom (espaces rognes)",
    )

    save_ui_prefs(
        prefs_dir,
        {"style": STYLE_GIFT, "recipient": "Adèle", "intro_done": True},
    )
    check(
        load_ui_prefs(prefs_dir)["intro_done"] is True,
        "prefs : intro terminee memorisee",
    )
    save_ui_prefs(prefs_dir, {"style": STYLE_SOBER, "recipient": "Adèle"})
    check(
        load_ui_prefs(prefs_dir)["intro_done"] is True,
        "prefs : changer de theme ne rejoue pas l'intro",
    )

    (prefs_dir / "ui_prefs.json").write_text('{"style": "neon"}', encoding="utf-8")
    check(
        load_ui_prefs(prefs_dir)["style"] == STYLE_GIFT,
        "prefs : style inconnu retombe sur le cadeau",
    )

    gift_css = theme_css(STYLE_GIFT)
    sober_css = theme_css(STYLE_SOBER)
    check(
        gift_css.startswith("<style>") and "</style>" in gift_css,
        "theme : bloc <style> complet",
    )
    check(
        "#FFFBF7" in gift_css and "#F6F7F9" in sober_css and gift_css != sober_css,
        "theme : palettes distinctes (gift chaleureux / sober neutre)",
    )
    check(
        "stButtonGroup" in gift_css and "stButtonGroup" in sober_css,
        "theme : selecteur d'apparence style dans les deux themes",
    )
    check(
        "st-key-bc-card" in gift_css and "st-key-bc-card" in sober_css,
        "theme : cartes stickers stylees dans les deux themes",
    )
    app_src = (Path(__file__).resolve().parent / "app.py").read_text(encoding="utf-8")
    check(
        'initial_sidebar_state="auto"' in app_src
        and "footer_html" not in app_src,
        "app : barre laterale auto sur telephone et pied de page retire",
    )
    check(
        "@media (max-width: 700px)" in gift_css
        and ".bc-hero-badges { display: none; }" in gift_css
        and '[data-testid="stMain"] [data-testid="column"]' in gift_css
        and "padding: 4rem" in gift_css,
        "theme : accueil mobile empile, badges masques, colonnes pleine largeur",
    )

    intro_path = INTRO_DIR / "index.html"
    intro_html = intro_path.read_text(encoding="utf-8") if intro_path.exists() else ""
    check(
        bool(intro_html)
        and "streamlit:componentReady" in intro_html
        and "streamlit:setComponentValue" in intro_html
        and "Ouvrir le cadeau" in intro_html
        and "Encore un cadeau" in intro_html
        and "Et c’est pas fini" in intro_html
        and "data-step=\"2\"" in intro_html
        and "Passer l’intro" not in intro_html
        and "id=\"chip\"" not in intro_html
        and "id=\"steps\"" not in intro_html
        and "TEXTS.tag" in intro_html,
        "unboxing : cadeaux un par un, sans etiquette ni compteur ni pastilles",
    )
    check(
        "bambucut_intro" in (INTRO_DIR.parent / "intro.py").read_text(encoding="utf-8")
        and "stSidebar" in INTRO_PAGE_CSS
        and "@media (max-width: 700px)" in INTRO_PAGE_CSS
        and "stVerticalBlock" in INTRO_PAGE_CSS,
        "unboxing : composant declare et plein ecran sans vide en haut",
    )
    defaults = load_intro_texts()
    check(
        defaults["cards"][0]["title"] == "Un kit stickers"
        and defaults["tag"] == "Pour {name}"
        and len(defaults["teasers"]) == 2
        and "{name}" in defaults["reveals"][2]["title"],
        "unboxing : textes par defaut charges",
    )
    custom_dir = OUT / "intro_texts"
    custom_dir.mkdir(parents=True, exist_ok=True)
    (custom_dir / "intro_texts.json").write_text(
        json.dumps(
            {
                "tag": "À ouvrir",
                "initial": {"title": "Coucou"},
                "cards": [{"title": "Perso"}],
                "buttons": {"open": "Go"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    custom = load_intro_texts(custom_dir)
    check(
        custom["initial"]["title"] == "Coucou"
        and custom["initial"]["subtitle"] == DEFAULT_INTRO_TEXTS["initial"]["subtitle"]
        and custom["tag"] == "À ouvrir"
        and custom["cards"][0]["title"] == "Perso"
        and custom["cards"][0]["pill"] == DEFAULT_INTRO_TEXTS["cards"][0]["pill"]
        and custom["buttons"]["open"] == "Go"
        and custom["buttons"]["finish"] == DEFAULT_INTRO_TEXTS["buttons"]["finish"],
        "unboxing : textes personnalises fusionnes avec les defauts",
    )
    broken_dir = OUT / "intro_texts_broken"
    broken_dir.mkdir(parents=True, exist_ok=True)
    (broken_dir / "intro_texts.json").write_text("{ pas du json", encoding="utf-8")
    check(
        load_intro_texts(broken_dir) == DEFAULT_INTRO_TEXTS,
        "unboxing : JSON casse -> valeurs par defaut",
    )
    check(
        "min-height: 100vh" in intro_html
        and "border-radius: 0" in intro_html
        and "env(safe-area-inset-bottom)" in intro_html
        and "mobileFrameHeight" in intro_html
        and "parent.innerHeight" in intro_html
        and "mergeTexts" in intro_html
        and "args.texts" in intro_html,
        "unboxing : plein ecran mobile et textes editables branches",
    )
    gift_hero = hero_html(STYLE_GIFT, "Adèle")
    check(
        "d’Adèle" in gift_hero and "Cadeau pour Adèle" in gift_hero,
        "hero : elision francaise et prenom affiche",
    )
    check(
        "&lt;script&gt;" in hero_html(STYLE_GIFT, "<script>x</script>")
        and "<script>x</script>" not in hero_html(STYLE_GIFT, "<script>x</script>"),
        "hero : prenom echappe (pas d'injection HTML)",
    )
    check(
        "BambuCut" in hero_html(STYLE_SOBER, "Adèle")
        and "d’Adèle" not in hero_html(STYLE_SOBER, "Adèle"),
        "hero : version sobre sans dedication",
    )
    base_readme = "BambuCut\n========"
    check(
        zip_readme(STYLE_GIFT, "Adèle", base_readme).startswith(
            "Un petit atelier pour Adèle"
        ),
        "zip : dedicace en mode cadeau",
    )
    check(
        zip_readme(STYLE_SOBER, "Adèle", base_readme) == base_readme
        and zip_readme(STYLE_GIFT, "", base_readme) == base_readme,
        "zip : LISEZMOI inchange en sobre ou sans prenom",
    )

    print("\n[5] Fichiers ecrits dans", OUT)
    if FAILURES:
        print(f"\n{len(FAILURES)} ECHEC(S) :")
        for failure in FAILURES:
            print("  -", failure)
        return 1
    print("\nTous les tests sont passes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Rendu PNG de previsualisation d'une planche (apercu web).

Legende des couleurs :
- stickers = visuel imprime ;
- damier clair = zone transparente (donc bordure blanche / papier) ;
- rouge vif = trajet de decoupe ;
- bleu = croix de calibrage ;
- gris = bords du plateau.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .models import MachineConfig
from .packing import Sheet

SCALE = 6.0  # pixels par mm (~1080 px pour 180 mm)
CUT_COLOR = (255, 0, 51)
CALIB_COLOR = (0, 102, 255)
PLATE_COLOR = (110, 110, 110)
GRID_COLOR = (232, 232, 232)
TEXT_COLOR = (80, 80, 80)


def _font(size: int = 14):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _mm_to_px(x_mm: float, y_mm: float, plate_h_mm: float) -> tuple[float, float]:
    """Repere mm bas-gauche -> pixels haut-gauche."""
    return x_mm * SCALE, (plate_h_mm - y_mm) * SCALE


def render_preview(
    sheet: Sheet,
    cfg: MachineConfig,
    total_sheets: int = 1,
    checker: bool = True,
    show_dimensions: bool = True,
    show_scale: bool = True,
) -> bytes:
    """Retourne le PNG de previsualisation d'une planche."""
    width = max(1, int(round(cfg.plate_w_mm * SCALE)))
    height = max(1, int(round(cfg.plate_h_mm * SCALE)))

    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # --- Fond damier (transparence) --------------------------------------
    if checker:
        step = max(4, int(round(5.0 * SCALE)))  # damier de 5 mm
        for row, y in enumerate(range(0, height, step)):
            for col, x in enumerate(range(0, width, step)):
                if (row + col) % 2 == 0:
                    draw.rectangle(
                        [x, y, min(x + step - 1, width - 1), min(y + step - 1, height - 1)],
                        fill=(246, 246, 246),
                    )

    # --- Grille legere tous les 10 mm ------------------------------------
    for x_mm in range(0, int(cfg.plate_w_mm) + 1, 10):
        x, _ = _mm_to_px(x_mm, 0, cfg.plate_h_mm)
        draw.line([(x, 0), (x, height)], fill=GRID_COLOR, width=1)
    for y_mm in range(0, int(cfg.plate_h_mm) + 1, 10):
        _, y = _mm_to_px(0, y_mm, cfg.plate_h_mm)
        draw.line([(0, y), (width, y)], fill=GRID_COLOR, width=1)

    # --- Stickers ---------------------------------------------------------
    for placement in sheet.placements:
        sticker = placement.sticker
        target_w = max(1, int(round(sticker.width_mm * SCALE)))
        target_h = max(1, int(round(sticker.height_mm * SCALE)))
        visual = sticker.image
        if visual.size != (target_w, target_h):
            visual = visual.resize((target_w, target_h), Image.Resampling.LANCZOS)
        x0 = int(round(placement.x_mm * SCALE))
        y0 = int(round((cfg.plate_h_mm - placement.y_mm - sticker.height_mm) * SCALE))
        image.paste(visual, (x0, y0), visual.getchannel("A"))

    # --- Tracés de decoupe (rouge vif) -----------------------------------
    for placement in sheet.placements:
        for contour in placement.sticker.outlines_mm:
            points = [
                _mm_to_px(
                    placement.x_mm + x,
                    placement.y_mm + y,
                    cfg.plate_h_mm,
                )
                for (x, y) in contour
            ]
            if len(points) >= 2:
                draw.line(points + [points[0]], fill=CUT_COLOR, width=2, joint="curve")

    # --- Cotes de chaque sticker (dimensions finies, bordure comprise) ---
    if show_dimensions:
        dim_font = _font(11)
        for placement in sheet.placements:
            sticker = placement.sticker
            text = f"{sticker.width_mm:.1f} x {sticker.height_mm:.1f} mm"
            bbox = draw.textbbox((0, 0), text, font=dim_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            pad = 3
            box_w = text_w + 2 * pad
            box_h = text_h + 2 * pad
            x0 = int(round(placement.x_mm * SCALE)) + 4
            y0 = int(round((cfg.plate_h_mm - placement.y_mm - sticker.height_mm) * SCALE)) + 4
            # Garde l'etiquette dans l'image du plateau.
            x0 = max(2, min(x0, width - box_w - 2))
            y0 = max(2, min(y0, height - box_h - 2))
            draw.rounded_rectangle(
                [x0, y0, x0 + box_w, y0 + box_h],
                radius=4,
                fill=(255, 255, 255),
                outline=(170, 170, 170),
                width=1,
            )
            draw.text(
                (x0 + pad - bbox[0], y0 + pad - bbox[1]),
                text,
                fill=(35, 35, 35),
                font=dim_font,
            )

    # --- Bords du plateau -------------------------------------------------
    draw.rectangle([0, 0, width - 1, height - 1], outline=PLATE_COLOR, width=2)

    # --- Croix de calibrage ----------------------------------------------
    cx, cy = _mm_to_px(cfg.calib_x_mm, cfg.calib_y_mm, cfg.plate_h_mm)
    arm = 4.0 * SCALE
    radius = 1.5 * SCALE
    draw.line([(cx - arm, cy), (cx + arm, cy)], fill=CALIB_COLOR, width=2)
    draw.line([(cx, cy - arm), (cx, cy + arm)], fill=CALIB_COLOR, width=2)
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=CALIB_COLOR,
        width=2,
    )
    draw.text(
        (cx + arm + 4, cy - 6),
        f"X{cfg.calib_x_mm:g} Y{cfg.calib_y_mm:g}",
        fill=CALIB_COLOR,
        font=_font(12),
    )

    # --- Cartouche --------------------------------------------------------
    legend_font = _font(13)
    draw.text(
        (8, 6),
        f"Planche {sheet.index}/{total_sheets} - {sheet.sticker_count} sticker(s) - "
        f"{cfg.plate_w_mm:g} x {cfg.plate_h_mm:g} mm",
        fill=TEXT_COLOR,
        font=legend_font,
    )
    draw.text(
        (8, height - 20),
        "rouge = decoupe   |   bleu = calibrage   |   damier = transparent (papier)",
        fill=TEXT_COLOR,
        font=_font(11),
    )

    # --- Regle d'echelle --------------------------------------------------
    if show_scale:
        if cfg.plate_w_mm >= 150:
            bar_mm = 50.0
        elif cfg.plate_w_mm >= 80:
            bar_mm = 25.0
        else:
            bar_mm = 10.0
        bar_px = max(8, int(round(bar_mm * SCALE)))
        bar_right = width - 16
        bar_left = bar_right - bar_px
        bar_y = height - 22
        draw.line([(bar_left, bar_y), (bar_right, bar_y)], fill=(45, 45, 45), width=3)
        for end_x in (bar_left, bar_right):
            draw.line(
                [(end_x, bar_y - 6), (end_x, bar_y + 6)],
                fill=(45, 45, 45),
                width=2,
            )
        draw.text(
            (bar_left, bar_y - 22),
            f"{bar_mm:g} mm",
            fill=TEXT_COLOR,
            font=_font(11),
        )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

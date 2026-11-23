"""Export PDF haute resolution (300 DPI, echelle 1:1) d'une planche.

Le PDF fait exactement la taille du plateau (180 x 180 mm par defaut) : a
l'impression, il faut choisir « 100 % » / « taille reelle » et desactivez
toute mise a l'echelle.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import MachineConfig
from .packing import Sheet


def _flatten_rgb(image: Image.Image) -> Image.Image:
    """Aplatit la transparence sur du blanc (papier)."""
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, (0, 0), image.getchannel("A"))
        return background
    return image.convert("RGB")


def _draw_calibration_mark(pdf: canvas.Canvas, cfg: MachineConfig) -> None:
    """Croix fine + cercle cible, exactement aux coordonnees de calibrage."""
    x = cfg.calib_x_mm
    y = cfg.calib_y_mm
    arm = 4.0  # mm de part et d'autre du centre
    pdf.saveState()
    pdf.setStrokeColorRGB(0.0, 0.0, 0.0)
    pdf.setLineWidth(0.25)
    pdf.line((x - arm) * mm, y * mm, (x + arm) * mm, y * mm)
    pdf.line(x * mm, (y - arm) * mm, x * mm, (y + arm) * mm)
    pdf.circle(x * mm, y * mm, 1.5 * mm, stroke=1, fill=0)
    pdf.restoreState()


def build_pdf(
    sheet: Sheet,
    cfg: MachineConfig,
    total_sheets: int = 1,
    generated_at: datetime | None = None,
) -> bytes:
    """Genere le PDF d'impression d'une planche (en memoire)."""
    buffer = BytesIO()
    page_w = cfg.plate_w_mm * mm
    page_h = cfg.plate_h_mm * mm
    stamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")

    pdf = canvas.Canvas(
        buffer,
        pagesize=(page_w, page_h),
        pageCompression=1,
        invariant=0,
    )
    pdf.setTitle(f"BambuCut - planche {sheet.index}")
    pdf.setAuthor("BambuCut")
    pdf.setSubject("Planche de stickers a imprimer a 100 %")
    pdf.setCreator("BambuCut")

    # Les stickers partagent souvent la meme image : on ne l'aplatit qu'une fois.
    cache: dict[int, ImageReader] = {}

    for placement in sheet.placements:
        sticker = placement.sticker
        key = id(sticker.image)
        reader = cache.get(key)
        if reader is None:
            reader = ImageReader(_flatten_rgb(sticker.image))
            cache[key] = reader
        pdf.drawImage(
            reader,
            placement.x_mm * mm,
            placement.y_mm * mm,
            width=sticker.width_mm * mm,
            height=sticker.height_mm * mm,
            preserveAspectRatio=False,
        )

    # Repere de calibrage (imprime, pas decoupe).
    _draw_calibration_mark(pdf, cfg)

    # Cartouche discret dans la marge basse.
    pdf.saveState()
    pdf.setFillGray(0.55)
    pdf.setFont("Helvetica", 3.2)
    pdf.drawString(
        2.0 * mm,
        1.6 * mm,
        f"BambuCut - planche {sheet.index}/{total_sheets} - "
        f"{cfg.plate_w_mm:g} x {cfg.plate_h_mm:g} mm - echelle 100 % - {stamp}",
    )
    pdf.restoreState()

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

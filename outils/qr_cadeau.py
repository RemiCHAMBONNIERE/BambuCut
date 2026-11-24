"""Genere le QR code et la carte a coller sur le premier carton.

Exemple :
    python outils/qr_cadeau.py "https://bambucut-adele.streamlit.app" --nom "Adele"

Le script produit :
    qr_cadeau.pdf      une page A4 avec une carte A6 centree et des traits de coupe
    qr_cadeau_qr.png   le QR seul (fond creme), pour une etiquette ou un montage
    qr_cadeau_qr.svg   le QR vectoriel, pour une impression nette

Dependances : reportlab (deja dans requirements.txt) et segno
(requirements-outils.txt).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

CARD_W = 105 * mm
CARD_H = 148 * mm
INK = HexColor("#332833")
MUTED = HexColor("#7D6A72")
CORAL = HexColor("#D9502E")
PINK = HexColor("#C2405F")
CREAM = HexColor("#FFFBF7")
LINE = HexColor("#F3D9C9")
CROP = HexColor("#B9AEA8")


def _fit(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> float:
    """Reduit la taille de police jusqu'a tenir dans ``max_w``."""
    while size > 6 and c.stringWidth(text, font, size) > max_w:
        size -= 0.5
    return size


def _url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("L'URL ne peut pas etre vide.")
    if not value.lower().startswith(("http://", "https://")):
        value = "https://" + value
    return value


def make_qr(url: str, out_dir: Path, stem: str) -> tuple[Path, Path]:
    """Ecrit le PNG et le SVG du QR code et retourne leurs chemins."""
    try:
        import segno
    except ImportError as exc:  # pragma: no cover - dependance optionnelle
        raise SystemExit(
            "Le module 'segno' est requis pour generer le QR.\n"
            "Installez-le avec : python -m pip install -r requirements-outils.txt"
        ) from exc

    qr = segno.make(url, error="h")
    png_path = out_dir / f"{stem}_qr.png"
    svg_path = out_dir / f"{stem}_qr.svg"
    qr.save(png_path, scale=24, border=2, dark="#1F1B24", light="#FFFBF7")
    qr.save(svg_path, scale=10, border=2, dark="#1F1B24", light="#FFFBF7")
    return png_path, svg_path


def make_card(
    url: str,
    name: str,
    title: str,
    qr_png: Path,
    out_pdf: Path,
) -> Path:
    """Dessine la carte A6 sur une page A4 avec traits de coupe."""
    page_w, page_h = A4
    card_x = (page_w - CARD_W) / 2
    card_y = (page_h - CARD_H) / 2
    center_x = card_x + CARD_W / 2
    top = card_y + CARD_H

    c = canvas.Canvas(str(out_pdf), pagesize=A4)
    c.setTitle(f"Un atelier pour {name}")
    c.setAuthor("BambuCut")

    # Carte creme et traits de coupe.
    c.setFillColor(CREAM)
    c.setStrokeColor(LINE)
    c.setLineWidth(1.1)
    c.roundRect(card_x, card_y, CARD_W, CARD_H, 6 * mm, stroke=1, fill=1)

    c.setStrokeColor(CROP)
    c.setLineWidth(0.4)
    gap = 2.5 * mm
    length = 5 * mm
    for x in (card_x, card_x + CARD_W):
        for y in (card_y, card_y + CARD_H):
            sx = -1 if x == card_x else 1
            sy = -1 if y == card_y else 1
            c.line(x + sx * gap, y, x + sx * (gap + length), y)
            c.line(x, y + sy * gap, x, y + sy * (gap + length))

    # En-tete.
    c.setStrokeColor(CORAL)
    c.setLineWidth(2.2)
    c.line(center_x - 9 * mm, top - 9 * mm, center_x + 9 * mm, top - 9 * mm)

    c.setFillColor(CORAL)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(center_x, top - 16 * mm, "B A M B U   C U T")

    title_size = _fit(c, title, "Times-Bold", 21, CARD_W - 20 * mm)
    c.setFillColor(INK)
    c.setFont("Times-Bold", title_size)
    c.drawCentredString(center_x, top - 27 * mm, title)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 11.5)
    c.drawCentredString(center_x, top - 37 * mm, "Scanne pour ouvrir le cadeau")

    # QR code : 62 mm, quiet zone incluse dans le PNG.
    qr_size = 62 * mm
    qr_x = center_x - qr_size / 2
    qr_y = card_y + 34 * mm
    c.drawImage(
        str(qr_png),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        mask="auto",
        preserveAspectRatio=True,
    )

    # Mode d'emploi et lien de secours.
    c.setFillColor(PINK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        center_x,
        card_y + 27 * mm,
        "SCANNE   ·   OUVRE LE CADEAU   ·   CRÉE TES STICKERS",
    )

    url_size = _fit(c, url, "Helvetica", 6.8, CARD_W - 22 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", url_size)
    c.drawCentredString(center_x, card_y + 19 * mm, url)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.8)
    c.drawCentredString(
        center_x,
        card_y + 10 * mm,
        "Garde ce carton : le lien reste valable.",
    )
    c.showPage()
    c.save()
    return out_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="URL publique de l'application")
    parser.add_argument("--nom", default="Adèle", help="Prenom affiche sur la carte")
    parser.add_argument(
        "--titre",
        default="Un atelier pour {nom}",
        help="Titre de la carte ({nom} est remplace)",
    )
    parser.add_argument(
        "--sortie",
        default="qr_cadeau",
        help="Racine des fichiers produits (ex. qr_cadeau ou dossier/qr)",
    )
    args = parser.parse_args(argv)

    try:
        url = _url(args.url)
    except ValueError as exc:
        parser.error(str(exc))

    name = (args.nom or "").strip()[:24] or "Adèle"
    output = Path(args.sortie)
    out_dir = output.parent if output.parent != Path("") else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = output.stem if output.suffix.lower() == ".pdf" else output.name
    pdf_path = out_dir / f"{stem}.pdf"

    qr_png, qr_svg = make_qr(url, out_dir, stem)
    make_card(url, name, args.titre.format(nom=name), qr_png, pdf_path)

    print("Carte prete :")
    print(f"  {pdf_path}  (A4, carte A6 + traits de coupe)")
    print(f"  {qr_png}")
    print(f"  {qr_svg}")
    print()
    print("Imprimez a 100 %, testez le scan avec un telephone, puis collez la carte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

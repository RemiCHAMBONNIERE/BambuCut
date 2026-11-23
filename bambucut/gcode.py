"""Generation du G-code de decoupe (drag knife) pour Bambu Lab A1 mini.

Securite : ce module n'emet JAMAIS de commande de chauffe (M104 / M109 /
M140 / M190), d'extrusion (parametre E), de nivellement (G29) ni de homing Z.
Chaque fichier produit est re-verifie par :func:`check_safety`.
"""

from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime

from .models import MachineConfig, Point, polyline_length_mm
from .packing import Sheet

FORBIDDEN_COMMANDS = {"M104", "M109", "M140", "M190", "G29"}
_E_PARAM = re.compile(r"(?:^|\s)E[-+]?(?:\d+\.?\d*|\.\d+)", re.IGNORECASE)


class GcodeError(ValueError):
    """Erreur de generation du G-code."""


def _fmt(value: float) -> str:
    """Format court et precis (3 decimales max, sans zeros inutiles)."""
    if not math.isfinite(float(value)):
        raise GcodeError("Coordonnee non finie detectee.")
    text = f"{float(value):.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _ascii(text: str, limit: int = 60) -> str:
    """Nettoie un commentaire G-code (ASCII, sans point-virgule, court)."""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace(";", ",").replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    return text[:limit]


def _outline(points: list[Point], tolerance: float = 0.02) -> list[Point]:
    """Supprime les doublons consecutifs et le point de fermeture en trop."""
    clean: list[Point] = []
    for x, y in points:
        if not clean:
            clean.append((float(x), float(y)))
            continue
        px, py = clean[-1]
        if abs(x - px) > tolerance or abs(y - py) > tolerance:
            clean.append((float(x), float(y)))
    if len(clean) > 1:
        fx, fy = clean[0]
        lx, ly = clean[-1]
        if abs(fx - lx) <= tolerance and abs(fy - ly) <= tolerance:
            clean.pop()
    return clean


def build_gcode(
    sheet: Sheet,
    cfg: MachineConfig,
    total_sheets: int = 1,
    generated_at: datetime | None = None,
) -> str:
    """Construit le programme de decoupe d'une planche."""
    stamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    z_cut = cfg.z_cut_mm
    z_travel = cfg.z_travel_mm
    f_cut = int(round(cfg.feed_cut))
    f_travel = int(round(cfg.feed_travel))
    f_plunge = int(round(cfg.plunge_feed))

    # Controle : le Z de securite final doit rester dans la plage de la A1 mini.
    z_park = z_travel + 20.0
    if z_park > 180:
        raise GcodeError(
            "Z de securite final (Z_TRAVEL + 20) superieur a 180 mm : "
            "reduisez Z_TRAVEL pour rester dans la course de la Bambu Lab A1 mini."
        )
    # Avancee du plateau en fin de programme : Y175 sur un plateau de 180 mm,
    # reduit automatiquement si une planche plus courte est configuree.
    park_y = min(175.0, max(0.0, cfg.plate_h_mm - 5.0))

    lines: list[str] = []
    add = lines.append

    add("; " + "=" * 64)
    add("; BambuCut - decoupe de stickers au traceur (drag knife)")
    add(f"; Planche {sheet.index}/{total_sheets} - plateau "
        f"{_fmt(cfg.plate_w_mm)} x {_fmt(cfg.plate_h_mm)} mm")
    add(f"; Genere le {stamp}")
    add(f"; {sheet.sticker_count} sticker(s) - {sheet.contour_count} contour(s) ferme(s)")
    add(f"; Repere de calibrage : X={_fmt(cfg.calib_x_mm)} Y={_fmt(cfg.calib_y_mm)} mm")
    add("; SECURITE : aucune chauffe, aucune extrusion (E), aucun nivellement (G29)")
    add("; Machine supposee homee ; la lame doit etre montee et le Z calibre avant lancement.")
    add("; " + "=" * 64)

    # --- En-tete machine -------------------------------------------------
    add("G21 ; unites en millimetres")
    add("G90 ; coordonnees absolues")
    if cfg.home_xy:
        add("G28 X Y ; homing X/Y uniquement (jamais Z avec la lame)")
    add(f"G1 Z{_fmt(z_travel)} F{f_travel} ; montee en position de securite")

    # --- Decoupe ---------------------------------------------------------
    for index, placement in enumerate(sheet.placements, start=1):
        sticker = placement.sticker
        add("")
        add(
            f"; --- Sticker {index}/{sheet.sticker_count} : {_ascii(sticker.name)} "
            f"[{_fmt(sticker.width_mm)} x {_fmt(sticker.height_mm)} mm] ---"
        )

        for c_index, contour in enumerate(sticker.outlines_mm, start=1):
            local = _outline(contour)
            if len(local) < 3:
                continue
            world = [
                (
                    placement.x_mm + x + cfg.offset_x_mm,
                    placement.y_mm + y + cfg.offset_y_mm,
                )
                for (x, y) in local
            ]
            # On repart du premier point pour fermer exactement la boucle.
            sx, sy = world[0]

            add(f"; contour {c_index}/{len(sticker.outlines_mm)} - {len(world)} points")
            add(f"G0 X{_fmt(sx)} Y{_fmt(sy)} F{f_travel}")
            add(f"G1 Z{_fmt(z_cut)} F{f_plunge} ; descente de la lame")
            for x, y in world[1:]:
                add(f"G1 X{_fmt(x)} Y{_fmt(y)} F{f_cut}")
            add(f"G1 X{_fmt(sx)} Y{_fmt(sy)} F{f_cut} ; fermeture du contour")
            add(f"G1 Z{_fmt(z_travel)} F{f_travel} ; remontee de la lame")

    # --- Fin de programme ------------------------------------------------
    add("")
    add(f"G1 Z{_fmt(z_park)} F{f_travel} ; remontee de securite (Z_TRAVEL + 20)")
    add(f"G0 Y{_fmt(park_y)} F{f_travel} ; avance du plateau pour retirer la feuille")
    add("; fin du programme")

    program = "\n".join(lines) + "\n"
    violations = check_safety(program)
    if violations:  # garde-fou : ne doit jamais arriver
        raise GcodeError("G-code refuse par le controle de securite : " + ", ".join(violations))
    return program


def check_safety(program: str) -> list[str]:
    """Retourne la liste des commandes interdites trouvees dans le programme."""
    problems: list[str] = []
    for number, raw in enumerate(program.splitlines(), start=1):
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        upper = code.upper()
        head = upper.split()[0]
        if head in FORBIDDEN_COMMANDS:
            problems.append(f"ligne {number}: {head}")
        if head.startswith("G28") and re.search(r"(?:^|\s)Z", upper):
            problems.append(f"ligne {number}: homing Z interdit")
        if head.startswith(("G0", "G1")) and _E_PARAM.search(upper):
            problems.append(f"ligne {number}: extrusion E")
    return problems


def cut_length_mm(sheet: Sheet) -> float:
    """Longueur totale de trace (information affichee dans l'interface)."""
    total = 0.0
    for placement in sheet.placements:
        for contour in placement.sticker.outlines_mm:
            total += polyline_length_mm(list(contour) + [contour[0]])
    return total


def out_of_bounds(sheet: Sheet, cfg: MachineConfig, tolerance: float = 0.05) -> list[str]:
    """Signale les contours qui sortiraient du plateau apres application des offsets."""
    messages: list[str] = []
    for index, placement in enumerate(sheet.placements, start=1):
        min_x = min(
            placement.x_mm + x + cfg.offset_x_mm
            for contour in placement.sticker.outlines_mm
            for (x, _) in contour
        )
        max_x = max(
            placement.x_mm + x + cfg.offset_x_mm
            for contour in placement.sticker.outlines_mm
            for (x, _) in contour
        )
        min_y = min(
            placement.y_mm + y + cfg.offset_y_mm
            for contour in placement.sticker.outlines_mm
            for (_, y) in contour
        )
        max_y = max(
            placement.y_mm + y + cfg.offset_y_mm
            for contour in placement.sticker.outlines_mm
            for (_, y) in contour
        )
        if (
            min_x < -tolerance
            or min_y < -tolerance
            or max_x > cfg.plate_w_mm + tolerance
            or max_y > cfg.plate_h_mm + tolerance
        ):
            messages.append(
                f"Planche {sheet.index}, sticker {index} ({_ascii(placement.sticker.name, 30)}) : "
                f"la coupe sort du plateau (X {min_x:.1f}..{max_x:.1f} / "
                f"Y {min_y:.1f}..{max_y:.1f} mm). Verifiez les offsets X/Y."
            )
    return messages

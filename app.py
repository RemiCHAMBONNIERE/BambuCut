"""BambuCut - genere des planches de stickers imprimables et le G-code de
decoupe (porte-lame / drag knife) pour une Bambu Lab A1 mini.

Lancement :
    python -m streamlit run app.py

Tout se pilote a la souris dans le navigateur : aucun argument en ligne de
commande, aucun fichier de configuration a editer a la main.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

from bambucut.config import (
    CONFIG_FILENAME,
    DEFAULTS,
    config_json_bytes,
    config_path,
    read_config,
    sanitize,
    write_config,
)
from bambucut.editor import editor_items, sheet_editor, thumbnail_data_url
from bambucut.gcode import build_gcode, cut_length_mm, out_of_bounds
from bambucut.geometry import prepare_sticker
from bambucut.intro import INTRO_PAGE_CSS, intro_screen
from bambucut.models import (
    BG_CUSTOM,
    BG_INHERIT,
    BG_MODES,
    BG_NONE,
    CONFIG_FIELDS,
    CORNER_ROUND,
    CORNER_SHARP,
    MachineConfig,
    StickerSpec,
    other_dimension_mm,
    resolve_bg_color,
    scaled_size_mm,
    target_size_mm,
)
from bambucut.packing import (
    layout_matches,
    overlapping_pairs,
    pack,
    sheets_from_layout,
)
from bambucut.pdf_export import build_pdf
from bambucut.preview import render_preview
from bambucut.theme import (
    STYLE_GIFT,
    STYLE_LABELS,
    STYLES,
    hero_html,
    load_ui_prefs,
    save_ui_prefs,
    theme_css,
    zip_readme,
)

APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = config_path(APP_DIR)
PREFS = load_ui_prefs(APP_DIR)

st.set_page_config(
    page_title=(
        f"BambuCut · stickers pour {PREFS['recipient']}"
        if PREFS["style"] == STYLE_GIFT and PREFS["recipient"]
        else "BambuCut - stickers & decoupe"
    ),
    page_icon="🎁" if PREFS["style"] == STYLE_GIFT else "🔪",
    layout="wide",
    initial_sidebar_state="auto",
)


# ---------------------------------------------------------------------------
# Etat de session
# ---------------------------------------------------------------------------
def init_state() -> None:
    """Initialise les cles de session (une seule fois par navigateur)."""
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(f"cfg_{key}", value)
    st.session_state.setdefault("stickers", [])
    st.session_state.setdefault("consumed_ids", [])
    st.session_state.setdefault("uploader_epoch", 0)
    st.session_state.setdefault("result", None)
    st.session_state.setdefault("layout", None)
    st.session_state.setdefault("bulk_bg_color", DEFAULTS["bg_color"])
    # Prefs relues a chaque session : l'intro terminee ou le theme choisi sont
    # pris en compte sans redemarrer le serveur.
    prefs = load_ui_prefs(APP_DIR)
    st.session_state.setdefault("ui_style", prefs["style"])
    st.session_state.setdefault("recipient", prefs["recipient"])
    st.session_state.setdefault("intro_done", prefs["intro_done"])
    st.session_state.setdefault("intro_run", 0)

    # Au premier affichage d'une session, on recharge automatiquement
    # config.json pour ne pas avoir a re-saisir les reglages machine.
    if not st.session_state.get("_cfg_bootstrapped"):
        st.session_state["_cfg_bootstrapped"] = True
        if CONFIG_FILE.exists():
            for key, value in read_config(CONFIG_FILE).items():
                st.session_state[f"cfg_{key}"] = value

    # Configuration en attente de chargement : appliquee AVANT les widgets.
    pending = st.session_state.pop("_pending_cfg", None)
    if pending is not None:
        for key, value in sanitize(pending).items():
            st.session_state[f"cfg_{key}"] = value
        st.session_state["bulk_bg_color"] = st.session_state["cfg_bg_color"]

    # Dimensions issues de l'editeur d'apercu : appliquees AVANT les widgets de
    # la liste (Streamlit interdit de modifier un widget deja instancie).
    pending_sizes = st.session_state.pop("_pending_sizes", None)
    if pending_sizes:
        for uid, size_mm in pending_sizes.items():
            if f"size_{uid}" in st.session_state:
                st.session_state[f"size_{uid}"] = float(size_mm)

    # Nettoyage des widgets des stickers supprimes au tour precedent.
    for uid in st.session_state.pop("_dead_uids", []):
        for prefix in ("mode_", "size_", "qty_", "bgm_", "bgc_"):
            st.session_state.pop(f"{prefix}{uid}", None)

    flash = st.session_state.pop("_flash", None)
    if flash:
        st.toast(flash, icon="✅")


init_state()


def current_style() -> str:
    style = str(st.session_state.get("ui_style") or PREFS["style"])
    return style if style in STYLES else STYLE_GIFT


def persist_ui_prefs() -> None:
    """Memorise le style, le prenom et l'etat de l'intro pour les prochaines sessions."""
    save_ui_prefs(
        APP_DIR,
        {
            "style": st.session_state.get("ui_style", PREFS["style"]),
            "recipient": st.session_state.get("recipient", PREFS["recipient"]),
            "intro_done": bool(
                st.session_state.get("intro_done", PREFS["intro_done"])
            ),
        },
    )


def replay_intro() -> None:
    """Relance l'unboxing depuis la barre laterale (nouvelle cle de composant)."""
    st.session_state["intro_done"] = False
    st.session_state["intro_run"] = int(st.session_state.get("intro_run", 0)) + 1
    persist_ui_prefs()


def cfg_from_state() -> MachineConfig:
    """Construit la configuration a partir des widgets de la barre laterale."""
    values = {key: st.session_state[f"cfg_{key}"] for key in CONFIG_FIELDS}
    return MachineConfig(**values)


def current_cfg_dict() -> dict:
    return {key: st.session_state[f"cfg_{key}"] for key in CONFIG_FIELDS}


def mode_label(value: str) -> str:
    return "Largeur cible (mm)" if value == "width" else "Hauteur cible (mm)"


def corner_label(value: str) -> str:
    return "Arrondis (recommande)" if value == CORNER_ROUND else "Vifs (mitre)"


def bg_mode_label(value: str) -> str:
    if value == BG_CUSTOM:
        return "Couleur personnalisée"
    if value == BG_NONE:
        return "Sans fond (bordure papier)"
    return "Comme le réglage global"


# ---------------------------------------------------------------------------
# Barre laterale
# ---------------------------------------------------------------------------
def render_sidebar() -> MachineConfig:
    with st.sidebar:
        st.title("⚙️ Réglages")
        st.caption("Tout est piloté à la souris. Les valeurs sont conservées dans `config.json`.")

        st.caption("Apparence")
        st.segmented_control(
            "Apparence",
            options=list(STYLES),
            format_func=lambda value: STYLE_LABELS.get(value, value),
            key="ui_style",
            on_change=persist_ui_prefs,
            label_visibility="collapsed",
            width="stretch",
            required=True,
        )
        if current_style() == STYLE_GIFT:
            recipient_name = str(st.session_state.get("recipient", "") or "").strip()[:24]
            if recipient_name:
                st.caption(f"🎁 Cadeau pour {recipient_name}")

        with st.expander("📐 Plateau & placement", expanded=True):
            col_a, col_b = st.columns(2)
            col_a.number_input(
                "Largeur (mm)", min_value=50.0, max_value=600.0, step=1.0,
                format="%.1f", key="cfg_plate_w_mm",
            )
            col_b.number_input(
                "Hauteur (mm)", min_value=50.0, max_value=600.0, step=1.0,
                format="%.1f", key="cfg_plate_h_mm",
            )
            col_c, col_d = st.columns(2)
            col_c.number_input(
                "Marge extérieure (mm)", min_value=0.0, max_value=60.0, step=0.5,
                format="%.1f", key="cfg_margin_mm",
            )
            col_d.number_input(
                "Espacement stickers (mm)", min_value=0.0, max_value=30.0, step=0.5,
                format="%.1f", key="cfg_spacing_mm",
            )
            st.checkbox(
                "Autoriser la rotation à 90° (optimise le remplissage)",
                key="cfg_allow_rotation",
            )

        with st.expander("🩹 Bordures & lissage", expanded=True):
            st.number_input(
                "Épaisseur de la bordure blanche (mm)",
                min_value=0.0, max_value=15.0, step=0.1, format="%.1f",
                key="cfg_border_mm",
                help="Buffer géométrique appliqué autour de la silhouette de chaque sticker.",
            )
            st.slider(
                "Lissage du contour (mm)",
                min_value=0.0, max_value=1.5, step=0.05,
                key="cfg_simplify_mm",
                help="Tolérance Douglas-Peucker. Plus la valeur est grande, plus la "
                     "découpe est fluide (et moins fidèle aux petits détails).",
            )
            st.selectbox(
                "Angles de la bordure",
                options=[CORNER_ROUND, CORNER_SHARP],
                format_func=corner_label,
                key="cfg_corner_style",
            )

        with st.expander("🎨 Fond & cotes", expanded=True):
            st.checkbox(
                "Fond de couleur sous les stickers",
                key="cfg_bg_enabled",
                help="Remplit toute la forme découpée (bordure comprise) avec la "
                     "couleur choisie, puis pose le visuel par-dessus.",
            )
            st.color_picker(
                "Couleur de fond",
                key="cfg_bg_color",
                disabled=not st.session_state.cfg_bg_enabled,
            )
            st.caption(
                "La couleur s'arrête exactement au tracé de découpe. "
                "Chaque sticker peut avoir sa propre couleur (fiche du sticker) ; "
                "désactivez cette option pour une bordure papier/blanche."
            )
            st.checkbox(
                "Afficher les cotes sur l'aperçu",
                key="cfg_show_dimensions",
                help="Affiche la taille finie de chaque sticker (bordure comprise).",
            )
            st.checkbox(
                "Afficher la règle d'échelle",
                key="cfg_show_scale",
                help="Ajoute une barre d'échelle en bas à droite de l'aperçu.",
            )

        with st.expander("🎯 Calibrage Bambu Lab A1 mini", expanded=True):
            col_e, col_f = st.columns(2)
            col_e.number_input(
                "Repère X (mm)", min_value=0.0, max_value=400.0, step=0.5,
                format="%.1f", key="cfg_calib_x_mm",
                help="Position de la croix de calibrage, depuis le coin bas-gauche.",
            )
            col_f.number_input(
                "Repère Y (mm)", min_value=0.0, max_value=400.0, step=0.5,
                format="%.1f", key="cfg_calib_y_mm",
            )
            col_g, col_h = st.columns(2)
            col_g.number_input(
                "Offset X buse → lame (mm)", min_value=-30.0, max_value=30.0,
                step=0.1, format="%.2f", key="cfg_offset_x_mm",
            )
            col_h.number_input(
                "Offset Y buse → lame (mm)", min_value=-30.0, max_value=30.0,
                step=0.1, format="%.2f", key="cfg_offset_y_mm",
            )
            st.caption("Le décalage est ajouté à chaque coordonnée de coupe du G-code.")

        with st.expander("🔪 Axe Z & vitesses", expanded=True):
            col_i, col_j = st.columns(2)
            col_i.number_input(
                "Z de coupe (mm)", min_value=0.0, max_value=150.0, step=0.1,
                format="%.2f", key="cfg_z_cut_mm",
            )
            col_j.number_input(
                "Z de déplacement (mm)", min_value=0.5, max_value=150.0, step=0.1,
                format="%.2f", key="cfg_z_travel_mm",
            )
            col_k, col_l = st.columns(2)
            col_k.number_input(
                "Vitesse de coupe (mm/min)", min_value=100, max_value=12000,
                step=100, key="cfg_feed_cut",
            )
            col_l.number_input(
                "Vitesse de déplacement (mm/min)", min_value=100, max_value=20000,
                step=100, key="cfg_feed_travel",
            )
            st.number_input(
                "Vitesse de descente de la lame (mm/min)",
                min_value=50, max_value=5000, step=50, key="cfg_plunge_feed",
            )
            st.checkbox(
                "Inclure `G28 X Y` au début du G-code (homing X/Y seulement)",
                key="cfg_home_xy",
                help="Utile si la machine n'est pas déjà homée. Le Z n'est jamais "
                     "homé automatiquement pour ne pas planter la lame.",
            )

        st.divider()
        st.subheader("💾 Configuration")
        col_save, col_load = st.columns(2)
        if col_save.button("💾 Enregistrer", help=f"Écrit {CONFIG_FILENAME}"):
            path = write_config(current_cfg_dict(), CONFIG_FILE)
            st.success(f"Enregistré dans {path.name}")

        if col_load.button("📂 Charger"):
            if CONFIG_FILE.exists():
                st.session_state["_pending_cfg"] = read_config(CONFIG_FILE)
                st.session_state["_flash"] = "Configuration chargée depuis config.json"
            else:
                st.session_state["_flash"] = "Aucun config.json : valeurs par défaut"
            st.rerun()

        st.download_button(
            "⬇️ Télécharger config.json",
            data=config_json_bytes(current_cfg_dict()),
            file_name=CONFIG_FILENAME,
            mime="application/json",
        )
        st.caption(f"Fichier local : `{CONFIG_FILE}`")

        cfg = cfg_from_state()
        problems = cfg.problems()
        if problems:
            st.error("⚠️ " + "\n\n- ".join(["Réglages incohérents :"] + problems))

        # Tout en bas de la barre laterale : rejouer l'unboxing.
        if current_style() == STYLE_GIFT:
            st.divider()
            st.button(
                "🎁 Revoir l'unboxing",
                key="replay_intro_btn",
                width="stretch",
                on_click=replay_intro,
                help="Rejoue la petite scène d'ouverture du cadeau.",
            )

        return cfg


# ---------------------------------------------------------------------------
# Gestion de la liste des stickers
# ---------------------------------------------------------------------------
def default_size_mm(aspect: float, cfg: MachineConfig) -> float:
    """Taille de depart raisonnable qui tient sur le plateau."""
    usable = max(
        5.0,
        min(cfg.usable_w_mm, cfg.usable_h_mm) - 2.0 * cfg.border_mm - cfg.spacing_mm,
    )
    limit = usable * min(1.0, max(aspect, 1e-6))
    return round(max(5.0, min(45.0, limit)), 1)


def content_aspect(image: Image.Image, fallback: float = 1.0) -> float:
    """Ratio largeur/hauteur du contenu visible (canal alpha recadre).

    C'est exactement le ratio utilise par :func:`prepare_sticker`, donc les
    dimensions affichees dans la liste correspondent a la vraie decoupe.
    """
    try:
        alpha = np.asarray(image.convert("RGBA").getchannel("A"))
        ys, xs = np.nonzero(alpha > 8)
    except Exception:
        return fallback
    if xs.size == 0:
        return fallback
    width = int(xs.max() - xs.min() + 1)
    height = int(ys.max() - ys.min() + 1)
    if width <= 0 or height <= 0:
        return fallback
    return width / height


def handle_uploads(uploaded, cfg: MachineConfig) -> None:
    """Ajoute les fichiers nouvellement deposes (sans doublon ni re-ajout)."""
    if not uploaded:
        st.session_state.consumed_ids = []
        return

    current: dict[str, object] = {}
    for uploaded_file in uploaded:
        file_id = getattr(uploaded_file, "file_id", None)
        if not file_id:
            file_id = hashlib.sha1(
                uploaded_file.name.encode("utf-8") + uploaded_file.getvalue()
            ).hexdigest()
        current[str(file_id)] = uploaded_file

    consumed = set(st.session_state.consumed_ids) & set(current)

    for file_id, uploaded_file in current.items():
        if file_id in consumed:
            continue

        data = uploaded_file.getvalue()
        try:
            with Image.open(io.BytesIO(data)) as probe:
                probe.load()
                width_px, height_px = probe.size
                aspect = content_aspect(probe, fallback=width_px / max(1, height_px))
        except Exception as exc:
            st.error(f"« {uploaded_file.name} » n'est pas une image lisible ({exc}).")
            consumed.add(file_id)
            continue

        uid = hashlib.sha1(data).hexdigest()[:12]
        if any(item["uid"] == uid for item in st.session_state.stickers):
            consumed.add(file_id)
            continue

        st.session_state[f"mode_{uid}"] = "width"
        st.session_state[f"size_{uid}"] = default_size_mm(aspect, cfg)
        st.session_state[f"qty_{uid}"] = 1
        st.session_state[f"bgm_{uid}"] = BG_INHERIT
        st.session_state[f"bgc_{uid}"] = st.session_state.get(
            "cfg_bg_color", DEFAULTS["bg_color"]
        )
        st.session_state.stickers.append(
            {
                "uid": uid,
                "name": uploaded_file.name,
                "bytes": data,
                "w_px": int(width_px),
                "h_px": int(height_px),
                "aspect": float(aspect),
            }
        )
        consumed.add(file_id)

    st.session_state.consumed_ids = sorted(consumed)


def render_bulk_bg() -> None:
    """Barre 'appliquer à tous' pour la couleur de contour."""
    stickers = st.session_state.stickers
    with st.container(border=True, key="bc-card-bulk"):
        st.markdown("🎨 **Couleur de contour**")
        col_a, col_b, col_c, col_d = st.columns(
            [1.0, 1.15, 1.0, 0.9], vertical_alignment="center"
        )
        col_a.color_picker(
            "Couleur commune",
            key="bulk_bg_color",
            disabled=not stickers,
            label_visibility="collapsed",
        )
        if col_b.button(
            "Couleur pour tous",
            key="bulk_apply_all",
            disabled=not stickers,
            help="Chaque sticker reçoit cette couleur (contour compris).",
        ):
            color = st.session_state["bulk_bg_color"]
            for item in stickers:
                st.session_state[f"bgm_{item['uid']}"] = BG_CUSTOM
                st.session_state[f"bgc_{item['uid']}"] = color
            st.session_state["_flash"] = "Couleur appliquée à tous les stickers"
            st.rerun()
        if col_c.button(
            "Suivre le global",
            key="bulk_inherit",
            disabled=not stickers,
            help="Tous les stickers suivent le réglage « Fond & cotes ».",
        ):
            for item in stickers:
                st.session_state[f"bgm_{item['uid']}"] = BG_INHERIT
            st.session_state["_flash"] = "Tous les stickers suivent le réglage global"
            st.rerun()
        if col_d.button(
            "Sans fond",
            key="bulk_none",
            disabled=not stickers,
            help="Bordure papier/blanche pour tous les stickers.",
        ):
            for item in stickers:
                st.session_state[f"bgm_{item['uid']}"] = BG_NONE
            st.session_state["_flash"] = "Aucun fond de couleur sur les stickers"
            st.rerun()
        st.caption(
            "Chaque sticker peut avoir sa propre couleur : réglez-la dans sa fiche. "
            "Ces boutons changent tous les stickers d'un coup."
        )


def render_sticker_list(cfg: MachineConfig) -> None:
    stickers = st.session_state.stickers
    st.subheader(f"🖼️ Stickers importés ({len(stickers)})")

    if not stickers:
        st.info(
            "Déposez un ou plusieurs PNG dans la zone ci-dessus. "
            "Les images sans transparence sont découpées en rectangle."
        )
        return

    render_bulk_bg()

    max_dim = float(min(cfg.plate_w_mm, cfg.plate_h_mm))
    border = float(cfg.border_mm)
    spacing = float(cfg.spacing_mm)
    usable_w = cfg.usable_w_mm
    usable_h = cfg.usable_h_mm

    for item in stickers:
        uid = item["uid"]
        aspect = float(item.get("aspect") or item["w_px"] / max(1, item["h_px"]))
        size_kb = max(1, len(item["bytes"]) // 1024)

        with st.container(border=True, key=f"bc-card-{uid}"):
            col_thumb, col_info, col_dim, col_qty, col_del = st.columns(
                [0.9, 2.4, 1.9, 1.3, 0.4], vertical_alignment="center"
            )

            col_thumb.image(item["bytes"], width=88)

            with col_info:
                st.markdown(f"**{item['name']}**")
                st.caption(
                    f"{item['w_px']} × {item['h_px']} px · "
                    f"ratio contenu {aspect:.3f} · {size_kb} Ko"
                )

            with col_dim:
                mode = st.selectbox(
                    "Mesure de référence",
                    options=["width", "height"],
                    format_func=mode_label,
                    key=f"mode_{uid}",
                )
                size_mm = st.number_input(
                    "Dimension (mm)",
                    min_value=5.0,
                    max_value=max(5.0, max_dim),
                    step=0.5,
                    format="%.1f",
                    key=f"size_{uid}",
                )

            with col_qty:
                st.number_input(
                    "Quantité",
                    min_value=1,
                    max_value=200,
                    step=1,
                    key=f"qty_{uid}",
                )
                other = other_dimension_mm(aspect, mode, float(size_mm))
                other_name = "Hauteur" if mode == "width" else "Largeur"
                est_w, est_h = target_size_mm(aspect, mode, float(size_mm))
                too_big = (
                    est_w + 2.0 * border + spacing > usable_w + 1e-6
                    or est_h + 2.0 * border + spacing > usable_h + 1e-6
                )
                st.caption(f"{other_name} : **{other:.1f} mm**")
                if too_big:
                    st.caption(":red[⚠ dépasse la zone utile]")

            if col_del.button("🗑️", key=f"del_{uid}", help="Retirer ce sticker"):
                st.session_state["_dead_uids"] = st.session_state.get("_dead_uids", []) + [uid]
                st.session_state.stickers = [
                    s for s in st.session_state.stickers if s["uid"] != uid
                ]
                st.rerun()

            col_mode, col_bgcolor = st.columns(
                [2.4, 1.6], vertical_alignment="center"
            )
            bg_mode = col_mode.selectbox(
                "Contour de ce sticker",
                options=list(BG_MODES),
                format_func=bg_mode_label,
                key=f"bgm_{uid}",
                help="La couleur remplit toute la forme découpée (bordure comprise) "
                     "et s'arrête exactement au tracé.",
            )
            col_bgcolor.color_picker(
                "Couleur",
                key=f"bgc_{uid}",
                disabled=bg_mode != BG_CUSTOM,
                label_visibility="collapsed",
            )


def collect_specs() -> list[StickerSpec]:
    specs: list[StickerSpec] = []
    default_color = st.session_state.get("cfg_bg_color", DEFAULTS["bg_color"])
    for item in st.session_state.stickers:
        uid = item["uid"]
        if f"mode_{uid}" not in st.session_state:
            continue
        specs.append(
            StickerSpec(
                uid=uid,
                name=item["name"],
                png_bytes=item["bytes"],
                width_px=item["w_px"],
                height_px=item["h_px"],
                mode=st.session_state[f"mode_{uid}"],
                size_mm=float(st.session_state[f"size_{uid}"]),
                qty=int(st.session_state[f"qty_{uid}"]),
                bg_mode=st.session_state.get(f"bgm_{uid}", BG_INHERIT),
                bg_color=st.session_state.get(f"bgc_{uid}", default_color),
            )
        )
    return specs


# ---------------------------------------------------------------------------
# Generation des planches
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False, max_entries=32)
def prepare_cached(
    png_bytes: bytes,
    name: str,
    mode: str,
    size_mm: float,
    border_mm: float,
    simplify_mm: float,
    corner_style: str,
    bg_color: str | None,
    uid: str,
):
    """Cache du traitement d'image (evite de recalculer a chaque clic)."""
    return prepare_sticker(
        png_bytes=png_bytes,
        name=name,
        mode=mode,
        size_mm=size_mm,
        border_mm=border_mm,
        simplify_mm=simplify_mm,
        corner_style=corner_style,
        bg_color=bg_color,
        uid=uid,
    )


def signature(cfg: MachineConfig, specs: list[StickerSpec]) -> str:
    payload = {
        "cfg": cfg.as_dict(),
        "specs": [
            [
                s.uid,
                s.mode,
                round(float(s.size_mm), 3),
                int(s.qty),
                resolve_bg_color(s.bg_mode, s.bg_color, cfg),
            ]
            for s in specs
        ],
    }
    return hashlib.sha1(
        json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    ).hexdigest()


ZIP_README = """BambuCut - contenu de l'archive
===================================

Pour chaque planche :
  planche_X_impression.pdf  -> a imprimer en 100 % / taille reelle (aucune mise a l'echelle)
  planche_X_decoupe.gcode   -> programme de decoupe (porte-lame)
  planche_X_previsu.png     -> apercu (rouge = decoupe, bleu = calibrage)

Impression
----------
- Papier blanc, format >= plateau (180 x 180 mm), impression sans marge si possible.
- Echelle 100 % imperativement : verifiez avec une regle que la croix de calibrage
  tombe bien a X=10 mm / Y=10 mm du coin bas-gauche.

Decoupe
-------
- Le G-code ne chauffe pas, n'extrude pas et ne nivelle pas.
- Machine homee, lame montee, Z_CUT/Z_TRAVEL calibres avant lancement.
- Le programme termine par Z_TRAVEL+20 puis Y175 pour retirer la feuille.
- Verifiez toujours la premiere planche a vide (Z_TRAVEL haut, sans papier) !
"""


def _is_rotated(sticker, base) -> bool:
    """Le sticker pose a-t-il ete tourne de 90 deg par rapport a l'original ?"""
    return base is not None and abs(sticker.width_mm - base.width_mm) > 1e-6


def generate_planches(
    specs: list[StickerSpec],
    cfg: MachineConfig,
    layout: list[dict] | None = None,
    checker: bool = True,
    recipient: str = "",
) -> dict:
    """Prepare, place et genere tous les fichiers. Leve ValueError si impossible.

    ``layout`` est une disposition manuelle (issue de l'editeur) : elle est
    utilisee telle quelle si elle couvre exactement les stickers demandes,
    sinon le placement automatique MaxRects reprend la main.
    """
    if not specs:
        raise ValueError("Ajoutez au moins une image avant de générer les planches.")

    prepared = []
    for spec in specs:
        prepared.append(
            prepare_cached(
                spec.png_bytes,
                spec.name,
                spec.mode,
                float(spec.size_mm),
                float(cfg.border_mm),
                float(cfg.simplify_mm),
                cfg.corner_style,
                resolve_bg_color(spec.bg_mode, spec.bg_color, cfg),
                spec.uid,
            )
        )

    prepared_by_uid: dict[str, object] = {}
    for spec, sticker in zip(specs, prepared):
        prepared_by_uid.setdefault(spec.uid, sticker)

    units = []
    expected: dict[str, int] = {}
    for spec, sticker in zip(specs, prepared):
        count = max(1, int(spec.qty))
        units.extend([sticker] * count)
        expected[spec.uid] = expected.get(spec.uid, 0) + count

    manual = layout_matches(layout, expected)
    sheets = sheets_from_layout(layout, prepared_by_uid, cfg) if manual else []
    if not sheets:
        manual = False
        sheets = pack(units, cfg)
    total_sheets = len(sheets)
    stamp = datetime.now()

    thumbs = {
        spec.uid: thumbnail_data_url(sticker.image) for spec, sticker in zip(specs, prepared)
    }
    base_sizes = {spec.uid: float(spec.size_mm) for spec in specs}
    base_widths = {
        spec.uid: float(sticker.width_mm) for spec, sticker in zip(specs, prepared)
    }

    warnings: list[str] = []
    if layout and not manual:
        warnings.append(
            "La disposition manuelle a été abandonnée : la liste, les quantités ou "
            "les dimensions ont changé depuis. Le placement automatique a été relancé."
        )

    payloads = []
    for sheet in sheets:
        pdf_bytes = build_pdf(sheet, cfg, total_sheets, stamp)
        gcode = build_gcode(sheet, cfg, total_sheets, stamp)
        preview_png = render_preview(
            sheet,
            cfg,
            total_sheets,
            checker=checker,
            show_dimensions=cfg.show_dimensions,
            show_scale=cfg.show_scale,
        )
        warnings.extend(out_of_bounds(sheet, cfg))
        pairs = overlapping_pairs(sheet)
        if pairs:
            warnings.append(
                f"Planche {sheet.index} : {len(pairs)} chevauchement(s) entre "
                "stickers. Déplacez-les dans l'éditeur ou relancez le placement "
                "automatique."
            )
        placements = [
            {
                "id": f"{sheet.index}:{position}",
                "uid": placement.sticker.uid,
                "name": placement.sticker.name,
                "x": placement.x_mm,
                "y": placement.y_mm,
                "w": placement.sticker.width_mm,
                "h": placement.sticker.height_mm,
                "rotated": _is_rotated(
                    placement.sticker, prepared_by_uid.get(placement.sticker.uid)
                ),
            }
            for position, placement in enumerate(sheet.placements)
        ]
        payloads.append(
            {
                "index": sheet.index,
                "count": sheet.sticker_count,
                "utilization": sheet.utilization(cfg),
                "cut_length_mm": cut_length_mm(sheet),
                "pdf": pdf_bytes,
                "gcode": gcode.encode("utf-8"),
                "preview": preview_png,
                "placements": placements,
            }
        )

    # Disposition reellement produite : point de depart de la prochaine edition.
    final_layout = []
    for sheet in sheets:
        entries = []
        for placement in sheet.placements:
            base = prepared_by_uid.get(placement.sticker.uid)
            entries.append(
                {
                    "uid": placement.sticker.uid,
                    "cx": placement.x_mm + placement.sticker.width_mm / 2.0,
                    "cy": placement.y_mm + placement.sticker.height_mm / 2.0,
                    "rotated": _is_rotated(placement.sticker, base),
                }
            )
        final_layout.append({"index": sheet.index, "placements": entries})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for payload in payloads:
            index = payload["index"]
            archive.writestr(f"planche_{index}_impression.pdf", payload["pdf"])
            archive.writestr(f"planche_{index}_decoupe.gcode", payload["gcode"])
            archive.writestr(f"planche_{index}_previsu.png", payload["preview"])
        archive.writestr(
            "config_utilisee.json",
            json.dumps(cfg.as_dict(), indent=2, ensure_ascii=False),
        )
        archive.writestr(
            "LISEZMOI.txt",
            zip_readme(current_style(), recipient, ZIP_README),
        )

    avg_util = sum(p["utilization"] for p in payloads) / max(1, len(payloads))
    return {
        "signature": signature(cfg, specs),
        "generated_at": stamp,
        "generated_label": stamp.strftime("%d/%m/%Y %H:%M:%S"),
        "sheets": payloads,
        "zip": zip_buffer.getvalue(),
        "sticker_count": len(units),
        "avg_utilization": avg_util,
        "total_cut_mm": sum(p["cut_length_mm"] for p in payloads),
        "warnings": warnings,
        "zip_name": f"planches_stickers_{stamp:%Y%m%d_%H%M}.zip",
        "thumbs": thumbs,
        "base_sizes": base_sizes,
        "base_widths": base_widths,
        "layout": final_layout,
        "manual_layout": manual,
        "plate_w_mm": float(cfg.plate_w_mm),
        "plate_h_mm": float(cfg.plate_h_mm),
    }


# ---------------------------------------------------------------------------
# Affichage des resultats
# ---------------------------------------------------------------------------
def apply_editor_edit(payload: dict, result: dict, cfg: MachineConfig) -> None:
    """Applique une edition de l'aperçu (tailles + positions).

    Les facteurs d'echelle deviennent des dimensions cibles dans les fiches ;
    les positions (centre de chaque sticker, en mm) forment une disposition
    manuelle qui sera utilisee telle quelle a la regeneration.
    """
    max_dim = float(min(cfg.plate_w_mm, cfg.plate_h_mm))
    base_sizes = result.get("base_sizes") or {}
    pending_sizes: dict[str, float] = {}
    for uid, scale in (payload.get("scales") or {}).items():
        uid = str(uid)
        base = base_sizes.get(uid)
        if base is None:
            continue
        try:
            pending_sizes[uid] = scaled_size_mm(
                base, float(scale), max_dim, extra_mm=2.0 * cfg.border_mm
            )
        except (TypeError, ValueError):
            continue

    positions = payload.get("positions") or {}
    layout: list[dict] = []
    moved = 0
    for sheet in result["sheets"]:
        entries = []
        for placement in sheet["placements"]:
            cx = placement["x"] + placement["w"] / 2.0
            cy = placement["y"] + placement["h"] / 2.0
            override = positions.get(str(placement.get("id")))
            if isinstance(override, dict):
                try:
                    cx = float(override.get("cx", cx))
                    cy = float(override.get("cy", cy))
                    moved += 1
                except (TypeError, ValueError):
                    pass
            entries.append(
                {
                    "uid": placement["uid"],
                    "cx": cx,
                    "cy": cy,
                    "rotated": bool(placement.get("rotated")),
                }
            )
        layout.append({"index": sheet["index"], "placements": entries})

    if not layout:
        return
    st.session_state["_pending_sizes"] = pending_sizes
    st.session_state["_pending_layout"] = layout
    st.session_state["_regenerate"] = True
    parts = []
    if pending_sizes:
        parts.append(f"{len(pending_sizes)} sticker(s) redimensionné(s)")
    if moved:
        parts.append(f"{moved} sticker(s) déplacé(s)")
    st.session_state["_flash"] = " · ".join(parts) + " — planche régénérée"
    st.rerun()


def render_editor(result: dict, cfg: MachineConfig) -> None:
    """Editeur interactif : deplacer et redimensionner directement sur l'aperçu."""
    sheets = result["sheets"]
    if not sheets:
        return

    with st.container(border=True, key="bc-card-editor"):
        st.markdown("#### ✏️ Déplacer / redimensionner sur l'aperçu")
        st.caption(
            "Glissez un sticker pour le **déplacer**, ses **coins rouges** pour le "
            "redimensionner (ratio conservé ; il glisse automatiquement pour rester "
            "dans la zone utile). Le chevauchement est autorisé pendant l'édition : "
            "« Appliquer l'édition » régénère la planche en conservant votre "
            "disposition. Toutes les copies d'une même image changent de taille "
            "ensemble. Les cotes sont les dimensions finies (bordure comprise)."
        )

        sig = str(result["signature"])[:10]
        options = [sheet["index"] for sheet in sheets]
        if len(options) > 1:
            index = st.selectbox(
                "Planche à éditer",
                options=options,
                format_func=lambda value: f"Planche {value} / {len(options)}",
                key=f"editor_sheet_{sig}",
            )
        else:
            index = options[0]

        gen = f"{sig}-{result['generated_at'].strftime('%H%M%S')}"
        payload = next(sheet for sheet in sheets if sheet["index"] == index)
        value = sheet_editor(
            items=editor_items(payload["placements"], result["thumbs"], index),
            plate_w=result["plate_w_mm"],
            plate_h=result["plate_h_mm"],
            usable={
                "x0": cfg.margin_mm,
                "y0": cfg.margin_mm,
                "w": cfg.usable_w_mm,
                "h": cfg.usable_h_mm,
            },
            sheet=index,
            total=len(sheets),
            gen=gen,
            theme=current_style(),
            key=f"editor_{gen}_{index}",
        )

        if isinstance(value, dict) and str(value.get("gen")) == gen:
            try:
                rev = float(value.get("rev") or 0)
            except (TypeError, ValueError):
                rev = 0.0
            rev_key = f"_editor_rev_{gen}_{index}"
            if rev > float(st.session_state.get(rev_key, 0)):
                st.session_state[rev_key] = rev
                if value.get("scales") or value.get("positions"):
                    apply_editor_edit(value, result, cfg)

        if result.get("manual_layout"):
            st.caption(
                "📌 Disposition manuelle active : elle est conservée à chaque "
                "regénération tant que la liste des images et les quantités restent "
                "les mêmes (les nouvelles tailles s'appliquent autour des centres)."
            )
        st.caption(
            "Pour repartir d'un placement optimisé (sans chevauchement), utilisez "
            "**♻️ Recalculer le placement automatique** ci-dessus."
        )


def render_results(cfg: MachineConfig, current_sig: str) -> None:
    result = st.session_state.get("result")
    if not result:
        return

    st.divider()
    st.subheader("📄 Planches générées")

    stale = result["signature"] != current_sig
    if stale:
        st.warning(
            "Les réglages, les dimensions ou la liste des stickers ont changé depuis "
            "cette génération. Mettez les fichiers à jour : la disposition manuelle "
            "est conservée si la liste et les quantités n'ont pas changé."
        )
        if st.button(
            "🔄 Mettre à jour les fichiers",
            type="primary",
            key="recalc_positions",
            help="Régénère PDF, G-code et aperçus avec les réglages actuels.",
        ):
            st.session_state["_regenerate"] = True
            st.rerun()

    if result["warnings"]:
        st.warning("\n\n".join(result["warnings"]))

    col_1, col_2, col_3, col_4 = st.columns(4)
    col_1.metric("Planches", len(result["sheets"]))
    col_2.metric("Stickers", result["sticker_count"])
    col_3.metric("Occupation moyenne", f"{result['avg_utilization'] * 100:.0f} %")
    col_4.metric("Longueur de coupe", f"{result['total_cut_mm'] / 1000:.2f} m")

    st.caption(f"Généré le {result['generated_label']} · réglages figés dans le ZIP.")

    col_zip, col_auto = st.columns([2.0, 1.6], vertical_alignment="center")
    col_zip.download_button(
        "📦 Tout télécharger (.ZIP)",
        data=result["zip"],
        file_name=result["zip_name"],
        mime="application/zip",
        type="primary",
        key="download_zip_all",
    )
    if col_auto.button(
        "♻️ Recalculer le placement automatique",
        key="recalc_auto",
        disabled=not result.get("manual_layout"),
        help="Abandonne la disposition manuelle et répartit tous les stickers "
             "avec MaxRects (aucun chevauchement, espacement respecté).",
    ):
        st.session_state["layout"] = None
        st.session_state["_regenerate"] = True
        st.rerun()

    render_editor(result, cfg)

    for sheet in result["sheets"]:
        index = sheet["index"]
        with st.container(border=True, key=f"bc-card-sheet-{index}"):
            st.markdown(
                f"#### Planche {index} / {len(result['sheets'])}"
            )
            st.caption(
                f"{sheet['count']} sticker(s) · occupation "
                f"{sheet['utilization'] * 100:.0f} % · longueur de coupe "
                f"{sheet['cut_length_mm'] / 1000:.2f} m"
            )
            st.image(
                sheet["preview"],
                caption="Aperçu : rouge = découpe, bleu = calibrage, damier = papier. "
                        "Cotes en mm, bordure comprise (non imprimées sur le PDF).",
            )
            dl_1, dl_2, dl_3 = st.columns(3)
            dl_1.download_button(
                "🖨️ PDF impression",
                data=sheet["pdf"],
                file_name=f"planche_{index}_impression.pdf",
                mime="application/pdf",
                key=f"download_pdf_{index}",
            )
            dl_2.download_button(
                "🔪 G-code découpe",
                data=sheet["gcode"],
                file_name=f"planche_{index}_decoupe.gcode",
                mime="text/plain",
                key=f"download_gcode_{index}",
            )
            dl_3.download_button(
                "🖼️ Prévisualisation PNG",
                data=sheet["preview"],
                file_name=f"planche_{index}_previsu.png",
                mime="image/png",
                key=f"download_png_{index}",
            )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
def render_intro(style: str) -> None:
    """Ecran d'unboxing plein cadre, affiche avant l'application."""
    recipient = str(st.session_state.get("recipient", "") or "").strip()[:24]
    st.markdown(theme_css(style), unsafe_allow_html=True)
    st.markdown(INTRO_PAGE_CSS, unsafe_allow_html=True)
    key = f"bc_intro_{int(st.session_state.get('intro_run', 0))}"
    value = intro_screen(recipient, style, key=key)
    if isinstance(value, dict) and value.get("done"):
        st.session_state["intro_done"] = True
        st.session_state["intro_run"] = int(st.session_state.get("intro_run", 0)) + 1
        save_ui_prefs(
            APP_DIR,
            {
                "style": st.session_state.get("ui_style", PREFS["style"]),
                "recipient": st.session_state.get("recipient", PREFS["recipient"]),
                "intro_done": True,
            },
        )
        st.rerun()


def main() -> None:
    style = current_style()
    if style == STYLE_GIFT and not st.session_state.get("intro_done"):
        render_intro(style)
        return

    cfg = render_sidebar()
    style = current_style()
    st.markdown(theme_css(style), unsafe_allow_html=True)
    recipient = str(st.session_state.get("recipient", "") or "").strip()[:24]
    st.markdown(hero_html(style, recipient), unsafe_allow_html=True)

    uploader_key = f"uploader_{st.session_state.uploader_epoch}"
    uploaded = st.file_uploader(
        "Déposez vos images ici (PNG recommandé, fond transparent)",
        type=["png", "webp", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=uploader_key,
    )
    handle_uploads(uploaded, cfg)

    render_sticker_list(cfg)
    specs = collect_specs()

    st.divider()
    col_gen, col_clear = st.columns([2.2, 1.0])
    total_qty = sum(spec.qty for spec in specs)
    regenerate = bool(st.session_state.pop("_regenerate", False))
    pending_layout = st.session_state.pop("_pending_layout", None)
    layout = pending_layout if pending_layout is not None else st.session_state.get("layout")
    generate_clicked = (
        col_gen.button(
            "🚀 Générer les planches",
            type="primary",
            disabled=not specs,
            help="Calcule le placement, les PDF, les G-code et les aperçus.",
        )
        or regenerate
    )
    if col_clear.button("🧹 Vider la liste"):
        st.session_state.stickers = []
        st.session_state.consumed_ids = []
        st.session_state.uploader_epoch += 1
        st.session_state["result"] = None
        st.session_state["layout"] = None
        st.rerun()

    if specs:
        st.caption(
            f"{len(specs)} image(s) · {total_qty} sticker(s) au total · "
            f"zone utile {cfg.usable_w_mm:.1f} × {cfg.usable_h_mm:.1f} mm"
        )
    else:
        st.caption("Ajoutez au moins une image pour activer la génération.")

    if generate_clicked:
        problems = cfg.problems()
        if problems:
            st.error("Corrigez d'abord les réglages : " + " ".join(problems))
        else:
            with st.spinner("Traitement des images, placement et génération des fichiers…"):
                try:
                    result = generate_planches(
                        specs,
                        cfg,
                        layout=layout,
                        recipient=recipient if style == STYLE_GIFT else "",
                    )
                except ValueError as exc:
                    st.session_state["result"] = None
                    st.error(f"❌ {exc}")
                except Exception as exc:  # pragma: no cover - filet de securite
                    st.session_state["result"] = None
                    st.error(f"Erreur inattendue pendant la génération : {exc}")
                    with st.expander("Détails techniques"):
                        st.exception(exc)
                else:
                    st.session_state["result"] = result
                    st.session_state["layout"] = (
                        result["layout"] if result["manual_layout"] else None
                    )
                    st.toast(
                        f"{len(result['sheets'])} planche(s) générée(s) !", icon="✅"
                    )

    render_results(cfg, signature(cfg, specs) if specs else "vide")

    with st.expander("ℹ️ Mode d'emploi & sécurité"):
        st.markdown(
            """
**1. Import** — déposez des PNG (fond transparent recommandé). Le ratio de chaque
image est strictement conservé : une seule dimension est choisie, l'autre est calculée.

**1 bis. Fond & cotes** — activez « Fond de couleur » pour remplir toute la forme
découpée (bordure comprise) ; la couleur s'arrête exactement au tracé. Dans chaque
fiche, le champ **Contour** permet de choisir une couleur par sticker (ou « sans
fond »), et la barre **Couleur de contour** applique une couleur à tous les stickers
d'un coup. Les cotes affichées sur l'aperçu sont les dimensions finies (bordure
comprise) ; elles ne sont pas imprimées dans le PDF.

**1 ter. Déplacer / redimensionner sur l'aperçu** — une fois les planches générées,
glissez un sticker pour le **déplacer**, ses **coins rouges** pour le
**redimensionner** (ratio conservé). Le chevauchement est autorisé pendant
l'édition. **✓ Appliquer l'édition** reporte les tailles dans la liste et
régénère la planche en conservant votre disposition ; **♻️ Recalculer le placement
automatique** replace tout sans chevauchement.

**2. Impression** — le PDF fait exactement la taille du plateau (180 × 180 mm).
Imprimez à **100 % / taille réelle**, sans « ajuster à la page ». Vérifiez ensuite que
la croix de calibrage tombe bien à 10 mm / 10 mm du coin bas-gauche.

**3. Découpe** — le G-code ne contient **aucune** chauffe, **aucune** extrusion et
**aucun** nivellement automatique. Il applique les offsets buse → lame et termine par
`Z = Z_TRAVEL + 20` puis `Y175`.

**Sécurité** — commencez toujours par un test « à vide » (lame relevée ou papier
retiré), vérifiez la hauteur de lame sur les quatre coins du plateau, et gardez la main
sur le bouton d'arrêt. Le Z n'est jamais homé automatiquement par ce fichier.
            """
        )


if __name__ == "__main__":
    main()

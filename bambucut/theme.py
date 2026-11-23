"""Habillage de l'interface (CSS injecte dans Streamlit).

Deux styles, sans aucun acces reseau (polices systeme uniquement) :

- ``gift``  : chaleureux et colore, pour la version offerte avec l'imprimante ;
- ``sober`` : neutre et sobre, pour l'usage quotidien.

Le choix et le prenom affiche sur la carte sont memorises dans
``ui_prefs.json``, a cote de ``config.json``, pour survivre aux rechargements.
Ce module n'importe pas Streamlit : il est testable sans interface.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

STYLE_GIFT = "gift"
STYLE_SOBER = "sober"
STYLES = (STYLE_GIFT, STYLE_SOBER)
STYLE_LABELS = {STYLE_GIFT: "🎁 Cadeau", STYLE_SOBER: "🧰 Sobre"}

PREF_FILENAME = "ui_prefs.json"
DEFAULT_RECIPIENT = "Adèle"


def prefs_path(base_dir: Path | str | None = None) -> Path:
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
    return root / PREF_FILENAME


def load_ui_prefs(base_dir: Path | str | None = None) -> dict:
    """Style, prenom et etat de l'intro (valeurs sures si le fichier est absent)."""
    try:
        data = json.loads(prefs_path(base_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    style = str(data.get("style") or "").strip().lower()
    if style not in STYLES:
        style = STYLE_GIFT
    recipient = str(data.get("recipient", DEFAULT_RECIPIENT) or "").strip()[:24]
    return {
        "style": style,
        "recipient": recipient,
        "intro_done": bool(data.get("intro_done", False)),
    }


def save_ui_prefs(base_dir: Path | str | None, prefs: dict) -> Path:
    style = str(prefs.get("style") or "").strip().lower()
    if style not in STYLES:
        style = STYLE_GIFT
    recipient = str(prefs.get("recipient", DEFAULT_RECIPIENT) or "").strip()[:24]
    # ``intro_done`` n'est pas fourni par les changements de theme : on conserve
    # alors l'etat deja enregistre, sinon l'unboxing reviendrait a chaque clic.
    intro_done = bool(prefs.get("intro_done", load_ui_prefs(base_dir)["intro_done"]))
    path = prefs_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "style": style,
                "recipient": recipient,
                "intro_done": intro_done,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


_VOWELS = "aàâäeéèêëiîïoôöuùûüy"


def _de(name: str) -> str:
    """« de » ou « d’ » selon l'initiale du prenom (Adèle -> d’Adèle)."""
    if not name:
        return ""
    first = name.lstrip()[:1].lower()
    return "d’" if first and first in _VOWELS + "h" else "de "


def hero_html(style: str, recipient: str = DEFAULT_RECIPIENT) -> str:
    """Bandeau d'accueil (gift) ou bloc titre sobre, en HTML."""
    name = html.escape((recipient or "").strip()[:24])
    if style == STYLE_GIFT:
        chip = f"🎁 Cadeau pour {name}" if name else "🎁 Un petit atelier"
        title = (
            f"Les stickers {_de(name)}{name}."
            if name
            else "Ton atelier de stickers."
        )
        return f"""
<div class="bc-hero">
  <div class="bc-hero-text">
    <span class="bc-chip">{chip}</span>
    <h1>{title}</h1>
    <p>Importe un PNG transparent, choisis sa taille : BambuCut prépare la planche
    à imprimer et le G-code qui fait découper les contours par la Bambu&nbsp;Lab
    A1&nbsp;mini. Tu n'as plus qu'à admirer le résultat.</p>
    <div class="bc-tags">
      <span>🖨️ Impression 1:1</span>
      <span>🔪 Découpe au traceur</span>
      <span>📦 ZIP prêt à imprimer</span>
    </div>
  </div>
  <div class="bc-hero-badges" aria-hidden="true">
    <span class="bc-badge">🖨️</span>
    <span class="bc-badge">✂️</span>
    <span class="bc-badge">✨</span>
  </div>
</div>
"""
    return """
<div class="bc-sober-head">
  <h1>🔪 BambuCut — stickers &amp; découpe</h1>
  <p>Importez vos PNG transparents, choisissez la taille de chaque sticker, puis
  générez les planches à imprimer et les fichiers G-code de découpe pour la
  Bambu Lab A1 mini.</p>
</div>
"""


_BASE = """
.block-container { padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1460px; }
.bc-hint { color: #666; font-size: 0.86rem; }
"""

# Adaptations communes aux deux themes pour un vrai usage au telephone.
_MOBILE = """
@media (max-width: 700px) {
  .block-container {
    max-width: 100% !important;
    padding: 4rem 0.75rem 2.5rem !important;
  }
  .bc-hero {
    flex-direction: column;
    align-items: stretch;
    gap: 0.8rem;
    padding: 1.25rem 1.15rem;
    border-radius: 22px;
    margin-bottom: 0.9rem;
  }
  .bc-hero-text { max-width: 100%; }
  .bc-hero h1 {
    font-size: clamp(1.55rem, 7.4vw, 2.05rem);
    line-height: 1.08;
    margin: 0.35rem 0 0.5rem;
  }
  .bc-hero p { font-size: 0.97rem; margin-bottom: 0.6rem; }
  .bc-hero-badges { display: none; }
  .bc-chip { font-size: 0.66rem; }
  .bc-tags span { font-size: 0.75rem; margin-right: 0.35rem; }
  h1 { font-size: 1.75rem; }
  h2 { font-size: 1.3rem; }
  h3 { font-size: 1.12rem; }
  /* Les colonnes Streamlit passent l'une sous l'autre : lisible au pouce. */
  [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
    flex-direction: column;
    gap: 0.45rem;
  }
  [data-testid="stMain"] [data-testid="column"] {
    width: 100% !important;
    flex: 1 1 100% !important;
    min-width: 0 !important;
  }
  [data-testid="stMain"] [data-testid="stFileUploaderDropzone"] {
    padding: 1rem 0.8rem;
  }
  [data-testid="stMain"] [data-testid="stFileUploaderDropzone"] button {
    width: 100%;
  }
}
"""

_GIFT = """
.stApp {
  background:
    radial-gradient(1100px 540px at 6% -12%, #FFE4D5 0%, rgba(255,228,213,0) 62%),
    radial-gradient(900px 500px at 102% -4%, #FFDDE9 0%, rgba(255,221,233,0) 58%),
    radial-gradient(1000px 640px at 45% 118%, #DCF4EC 0%, rgba(220,244,236,0) 60%),
    #FFFBF7;
}
.stApp::before {
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background-image: radial-gradient(rgba(255,138,91,0.13) 1px, transparent 1.5px);
  background-size: 24px 24px;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stHeader"] {
  background: transparent;
}
[data-testid="stMainBlockContainer"] { position: relative; z-index: 1; }

h1, h2, h3 {
  font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif !important;
  color: #332833 !important;
  letter-spacing: -0.015em;
}
h1 { font-size: 2.1rem; }
h2 { font-size: 1.45rem; }
h3 { font-size: 1.18rem; }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {
  color: #3C3038;
}
[data-testid="stCaptionContainer"] p { color: #8B7A80; }
a { color: #D94F7A !important; }
hr { border-color: #F0DFD2 !important; }

/* ---- barre laterale ---- */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #FFF4EB 0%, #FFFAF6 100%);
  border-right: 1px solid #F3E0D2;
}
[data-testid="stSidebar"] h1 { font-size: 1.4rem; }
[data-testid="stSidebar"] hr { border-color: #F1DECD !important; }
[data-testid="stSidebarUserContent"] { padding-top: 0.6rem; }

/* ---- cartes ---- */
[class*="st-key-bc-card"] {
  background: #FFFFFF !important;
  border: 1px solid #F4E2D6 !important;
  border-radius: 20px !important;
  box-shadow: 0 14px 34px rgba(163, 106, 80, 0.09);
  padding: 1.05rem 1.2rem !important;
}

/* ---- accueil ---- */
.bc-hero {
  position: relative; overflow: hidden;
  display: flex; gap: 1.5rem; align-items: center; justify-content: space-between;
  padding: 2rem 2.2rem;
  border-radius: 28px;
  border: 1px solid rgba(255, 255, 255, 0.75);
  background: linear-gradient(115deg, #FFE9DC 0%, #FFDCE8 48%, #DFF4ED 100%);
  box-shadow: 0 18px 44px rgba(196, 120, 120, 0.18);
  margin-bottom: 1.1rem;
}
.bc-hero-text { max-width: 64ch; }
.bc-hero h1 {
  font-size: clamp(1.9rem, 3vw, 2.7rem);
  line-height: 1.06;
  margin: 0.45rem 0 0.55rem;
}
.bc-hero p { color: #57454E; font-size: 1.02rem; margin: 0 0 0.7rem; }
.bc-chip {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.32rem 0.8rem; border-radius: 999px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 4px 12px rgba(194, 64, 95, 0.10);
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: #C2405F;
}
.bc-tags span {
  display: inline-block; margin: 0.15rem 0.45rem 0.15rem 0;
  padding: 0.32rem 0.72rem; border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.9);
  font-size: 0.8rem; color: #4B3B44;
}
.bc-hero-badges { display: flex; gap: 0.65rem; flex-shrink: 0; }
.bc-badge {
  width: 64px; height: 64px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.7rem;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 10px 24px rgba(180, 110, 90, 0.18);
  transform: rotate(-6deg);
}
.bc-badge:nth-child(2) { transform: rotate(6deg) translateY(10px); }
.bc-badge:nth-child(3) { transform: rotate(-3deg) translateY(-6px); }

/* ---- import ---- */
[data-testid="stFileUploaderDropzone"] {
  background: linear-gradient(120deg, #FFF7F1, #FFF1F6);
  border: 2px dashed #FFAE97;
  border-radius: 22px;
  padding: 1.15rem 1rem;
  transition: border-color 0.15s ease, background 0.15s ease;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: #FF6F91;
  background: linear-gradient(120deg, #FFF2E9, #FFE9F1);
}
[data-testid="stFileUploaderFile"] {
  background: #FFF8F3; border-radius: 12px;
}
[data-testid="stFileUploaderDropzone"] button { border-radius: 999px; }

/* ---- boutons ---- */
.stButton > button, .stDownloadButton > button,
[data-testid="stFileUploaderDropzone"] button {
  border-radius: 999px !important;
  font-weight: 600;
  transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
}
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #FF7A59, #FF5C8A) !important;
  border: none !important;
  color: #FFFFFF !important;
  box-shadow: 0 8px 20px rgba(255, 92, 138, 0.28);
}
[data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-1px);
  box-shadow: 0 12px 26px rgba(255, 92, 138, 0.36);
  color: #FFFFFF !important;
}
[data-testid="stBaseButton-secondary"] {
  background: #FFFFFF !important;
  border: 1px solid #F0DACB !important;
  color: #4A3B45 !important;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: #FFAE97 !important;
  color: #D94F7A !important;
}

/* ---- indicateurs ---- */
[data-testid="stMetric"] {
  background: #FFFFFF;
  border: 1px solid #F4E2D6;
  border-radius: 18px;
  padding: 0.85rem 1rem;
  box-shadow: 0 10px 24px rgba(163, 106, 80, 0.07);
}
[data-testid="stMetricValue"] { color: #E4572E; }
[data-testid="stMetricLabel"] p {
  text-transform: uppercase; letter-spacing: 0.09em;
  font-size: 0.7rem; font-weight: 600; color: #9C8A86;
}

/* ---- panneaux & champs ---- */
[data-testid="stExpander"] {
  background: #FFFFFF;
  border: 1px solid #F4E2D6 !important;
  border-radius: 16px !important;
  overflow: hidden;
}
[data-testid="stExpander"] summary { font-weight: 600; }
[data-testid="stNumberInputContainer"] { border-radius: 10px !important; }
[data-baseweb="input"], [data-baseweb="select"] > div {
  border-radius: 10px !important;
  border-color: #EEDBCE !important;
  background: #FFFDFB !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color: #FF9C86 !important;
  box-shadow: 0 0 0 3px rgba(255, 156, 134, 0.18) !important;
}
[data-baseweb="popover"] [role="listbox"] { border-radius: 12px; }
[data-testid="stAlertContainer"] { border-radius: 14px; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
  background: #FFF7F1 !important;
  border: 1px solid #F4E2D6 !important;
}

/* ---- selecteur d'apparence ---- */
[data-testid="stButtonGroup"] [role="radiogroup"] { gap: 0.45rem; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
  border-radius: 999px !important;
  border: 1px solid #F0DACB !important;
  background: #FFFFFF !important;
  color: #4A3B45 !important;
  padding: 0.3rem 0.85rem;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover {
  border-color: #FFAE97 !important;
  color: #D94F7A !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] {
  background: linear-gradient(135deg, #FF7A59, #FF5C8A) !important;
  border-color: transparent !important;
  box-shadow: 0 6px 16px rgba(255, 92, 138, 0.26);
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] * {
  color: #FFFFFF !important;
}
"""

_SOBER = """
.stApp { background: #F6F7F9; }
[data-testid="stAppViewContainer"], [data-testid="stMain"] { background: transparent; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: #FFFFFF;
  border-right: 1px solid #E6E8EC;
}
[data-testid="stSidebarUserContent"] { padding-top: 0.6rem; }
h1, h2, h3 { color: #1F2328 !important; letter-spacing: 0; }
h1 { font-size: 2rem; }
[data-testid="stCaptionContainer"] p { color: #6B7280; }
hr { border-color: #E6E8EC !important; }

[class*="st-key-bc-card"] {
  background: #FFFFFF !important;
  border: 1px solid #E3E6EB !important;
  border-radius: 12px !important;
  padding: 1rem 1.1rem !important;
}

.bc-sober-head { margin: 0.2rem 0 1rem; }
.bc-sober-head h1 { margin-bottom: 0.35rem; }
.bc-sober-head p { color: #5B6270; max-width: 80ch; }

[data-testid="stFileUploaderDropzone"] {
  background: #FFFFFF;
  border: 2px dashed #E4572E;
  border-radius: 14px;
}
.stButton > button, .stDownloadButton > button {
  border-radius: 8px !important;
  font-weight: 600;
}
[data-testid="stBaseButton-primary"] {
  background: #E4572E !important;
  border: none !important;
  color: #FFFFFF !important;
}
[data-testid="stBaseButton-primary"]:hover { background: #C9431F !important; color: #fff !important; }
[data-testid="stBaseButton-secondary"] {
  background: #FFFFFF !important;
  border: 1px solid #DDE1E7 !important;
  color: #333941 !important;
}
[data-testid="stBaseButton-secondary"]:hover {
  border-color: #E4572E !important; color: #C9431F !important;
}
[data-testid="stMetric"] {
  background: #FFFFFF; border: 1px solid #E3E6EB;
  border-radius: 10px; padding: 0.8rem 1rem;
}
[data-testid="stMetricValue"] { color: #C9431F; }
[data-testid="stMetricLabel"] p {
  text-transform: uppercase; letter-spacing: 0.07em;
  font-size: 0.72rem; color: #6B7280;
}
[data-testid="stExpander"] {
  background: #FFFFFF;
  border: 1px solid #E3E6EB !important;
  border-radius: 10px !important;
  overflow: hidden;
}
[data-testid="stNumberInputContainer"] { border-radius: 8px !important; }
[data-baseweb="input"], [data-baseweb="select"] > div { border-radius: 8px !important; }
[data-testid="stAlertContainer"] { border-radius: 8px; }
[data-testid="stButtonGroup"] [role="radiogroup"] { gap: 0.4rem; }
[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
  border-radius: 8px !important;
  border: 1px solid #DDE1E7 !important;
  background: #FFFFFF !important;
  color: #333941 !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] {
  background: #E4572E !important;
  border-color: transparent !important;
}
[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected="true"] * {
  color: #FFFFFF !important;
}
"""


def theme_css(style: str) -> str:
    """Bloc ``<style>`` complet pour le style demande."""
    palette = _GIFT if style == STYLE_GIFT else _SOBER
    return f"<style>\n{_BASE}\n{palette}\n{_MOBILE}\n</style>"


def zip_readme(style: str, recipient: str, base_readme: str) -> str:
    """Ajoute une dedicace au LISEZMOI du ZIP en mode cadeau."""
    name = (recipient or "").strip()[:24]
    if style != STYLE_GIFT or not name:
        return base_readme
    banner = (
        f"Un petit atelier pour {name}\n"
        + "=" * (24 + len(name))
        + "\n\n"
    )
    return banner + base_readme

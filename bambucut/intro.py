"""Ecran d'accueil « unboxing » (composant Streamlit local, sans npm).

Affiche un cadeau ferme, puis revele un a un le kit stickers, l'application et
l'imprimante, avec un ecran d'attente « Un cadeau t'attend » entre chaque. Le
composant ne renvoie a Streamlit qu'un booleen ``done`` lorsque l'on entre dans
l'atelier ; l'application memorise alors ce choix dans ``ui_prefs.json`` pour ne
plus reafficher l'intro.

Les textes affiches sont lus dans ``intro_texts.json`` (a la racine du projet) :
on peut les modifier sans toucher au code, puis recharger la page. Le fichier est
fusionne avec les valeurs par defaut ci-dessous, donc une cle oubliee ne casse
rien.

Comme l'editeur d'apercu, le protocole de composant est implemente a la main :
aucune compilation, aucun paquet npm, aucun acces reseau.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parent / "intro_component"
INTRO_TEXTS_FILENAME = "intro_texts.json"

_component = None

DEFAULT_INTRO_TEXTS: dict = {
    "tag": "Pour {name}",
    "initial": {
        "note": "",
        "title": "Un cadeau t’attend.",
        "subtitle": "Ouvre-le pour découvrir ce qu’il y a dedans.",
    },
    "teasers": [
        {
            "note": "Et c’est pas fini…",
            "title": "Un deuxième cadeau, rien que pour toi.",
            "subtitle": "",
        },
        {
            "note": "Et c’est pas fini…",
            "title": "Le dernier, et pas des moindres.",
            "subtitle": "",
        },
    ],
    "reveals": [
        {
            "title": "Premier cadeau.",
            "subtitle": "Ouvre la boîte : tout est là pour commencer.",
        },
        {
            "title": "Deuxième cadeau.",
            "subtitle": "Celui-là, tu l’as déjà entre les mains.",
        },
        {
            "title": "Tout est prêt, {name}.",
            "subtitle": "Il ne te reste plus qu’à importer ton premier dessin.",
        },
    ],
    "cards": [
        {
            "title": "Un kit stickers",
            "text": (
                "Feuilles, lame et mode d’emploi : tout est là pour ta première "
                "planche."
            ),
            "pill": "✂️ Le matériel",
        },
        {
            "title": "L’atelier BambuCut",
            "text": (
                "Cette application : dépose un PNG, choisis la taille, elle "
                "prépare le PDF et le G-code."
            ),
            "pill": "🎨 L’application",
        },
        {
            "title": "La Bambu Lab A1 mini",
            "text": (
                "Une vraie imprimante 3D : elle fabrique tout ce que tu veux, et "
                "avec le porte-lame elle découpe aussi tes planches de stickers."
            ),
            "pill": "🖨️ Impression 3D + découpe",
        },
    ],
    "buttons": {
        "open": "Ouvrir le cadeau 🎁",
        "next": "Encore un cadeau →",
        "finish": "Entrer dans l’atelier →",
    },
}

# CSS injecte dans la page Streamlit pendant l'intro : plein ecran, sans barre
# laterale ni en-tete, pour que le cadeau soit le seul sujet de l'ecran. Sur
# telephone, on retire toute gouttiere pour un vrai plein ecran.
INTRO_PAGE_CSS = """<style>
[data-testid="stSidebar"],
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
  display: none !important;
}
[data-testid="stMainBlockContainer"], .block-container {
  max-width: 1180px !important;
  padding-top: 0.5rem !important;
  padding-bottom: 1.2rem !important;
}
[data-testid="stAppViewContainer"], [data-testid="stMain"] {
  background: transparent;
}
@media (max-width: 700px) {
  [data-testid="stMainBlockContainer"], .block-container {
    max-width: 100% !important;
    padding: 0 !important;
    gap: 0 !important;
  }
  /* Les blocs vides au-dessus du composant ajoutaient 32 px de vide. */
  [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {
    gap: 0 !important;
  }
  [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background: #FFFBF7 !important;
  }
}
</style>"""


def intro_texts_path(base_dir: Path | str | None = None) -> Path:
    """Chemin de ``intro_texts.json`` (racine du projet par defaut)."""
    root = (
        Path(base_dir)
        if base_dir is not None
        else Path(__file__).resolve().parent.parent
    )
    return root / INTRO_TEXTS_FILENAME


def _merge_texts(defaults, data):
    """Fusionne les textes lus avec les valeurs par defaut, cle par cle."""
    if isinstance(defaults, dict):
        if not isinstance(data, dict):
            return copy.deepcopy(defaults)
        return {key: _merge_texts(value, data.get(key)) for key, value in defaults.items()}
    if isinstance(defaults, list):
        if not isinstance(data, list):
            return copy.deepcopy(defaults)
        return [
            _merge_texts(item, data[index] if index < len(data) else None)
            for index, item in enumerate(defaults)
        ]
    if isinstance(defaults, str):
        return data if isinstance(data, str) else defaults
    return copy.deepcopy(defaults)


def load_intro_texts(base_dir: Path | str | None = None) -> dict:
    """Textes de l'intro (valeurs sures si le fichier est absent ou casse)."""
    try:
        data = json.loads(intro_texts_path(base_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return _merge_texts(DEFAULT_INTRO_TEXTS, data)


def _get_component():
    """Declare le composant au premier appel (necessite un ScriptRunContext)."""
    global _component
    if _component is None:
        import streamlit.components.v1 as components

        _component = components.declare_component(
            "bambucut_intro", path=str(COMPONENT_DIR)
        )
    return _component


def intro_screen(
    recipient: str,
    theme: str = "gift",
    texts: dict | None = None,
    key: str = "bc_intro",
) -> dict | None:
    """Affiche l'unboxing et retourne ``{"done": True}`` quand il est termine."""
    return _get_component()(
        recipient=str(recipient or ""),
        theme=str(theme),
        texts=texts if texts is not None else load_intro_texts(),
        key=key,
        default=None,
    )

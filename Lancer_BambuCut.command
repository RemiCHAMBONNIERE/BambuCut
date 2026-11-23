#!/bin/bash
# Double-cliquez sur ce fichier pour lancer BambuCut (macOS / Linux).
# La premiere fois : clic droit > Ouvrir (ou chmod +x Lancer_BambuCut.command).
set -e
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "============================================================"
    echo "  Premiere utilisation : installation de BambuCut"
    echo "  Cela peut prendre 1 a 3 minutes, une seule fois."
    echo "============================================================"
    python3 -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
elif ! .venv/bin/python -c "import streamlit, cv2, shapely, reportlab, numpy, PIL" >/dev/null 2>&1; then
    echo "Mise a jour des dependances..."
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

echo ""
echo "Demarrage de BambuCut... Le navigateur va s'ouvrir automatiquement."
echo "Pour arreter l'application : fermez cette fenetre ou faites Ctrl+C."
echo ""
exec .venv/bin/python -m streamlit run app.py

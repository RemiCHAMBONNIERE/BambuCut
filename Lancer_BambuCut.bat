@echo off
setlocal
chcp 65001 >nul
title BambuCut
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ============================================================
    echo   Premiere utilisation : installation de BambuCut
    echo   Cela peut prendre 1 a 3 minutes, une seule fois.
    echo ============================================================
    echo.
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if not exist "%PYTHON%" (
        echo.
        echo ERREUR : Python 3.10 ou plus recent est introuvable.
        echo Installez-le depuis https://www.python.org/downloads/windows/
        echo en cochant "Add Python to PATH", puis relancez ce fichier.
        pause
        exit /b 1
    )
    "%PYTHON%" -m pip install --upgrade pip
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERREUR pendant l'installation des dependances.
        pause
        exit /b 1
    )
)

rem Verifie que le venv contient bien toutes les dependances (venv incomplet,
rem mise a jour du projet...). Repare automatiquement si besoin.
"%PYTHON%" -c "import streamlit, cv2, shapely, reportlab, numpy, PIL" >nul 2>nul
if errorlevel 1 (
    echo.
    echo Installation / mise a jour des dependances...
    "%PYTHON%" -m pip install --upgrade pip
    "%PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERREUR pendant l'installation des dependances.
        echo Si le message parle de "nom de fichier trop long", verifiez que
        echo l'installation se fait bien dans .venv et non dans le Python global.
        pause
        exit /b 1
    )
)

echo.
echo Demarrage de BambuCut... Le navigateur va s'ouvrir automatiquement.
echo Pour arreter l'application : fermez cette fenetre ou faites Ctrl+C.
echo.
"%PYTHON%" -m streamlit run app.py

if errorlevel 1 (
    echo.
    echo L'application s'est arretee avec une erreur.
)
pause

#!/usr/bin/env bash
# ==============================================================================
# Script de construction de Bobine.app + Bobine.dmg (macOS)
# PortabiliteCrossPlatformX — Lot 3
#
# NE PEUT ÊTRE EXÉCUTÉ QUE SUR UNE VRAIE MACHINE macOS — PyInstaller ne
# cross-compile pas (aucun bundle macOS ne peut être produit depuis Linux ou
# Windows). NON TESTÉ dans cet état (écrit d'après la documentation
# PyInstaller/Apple) ; à valider au premier passage du job CI `macos-build`
# (.github/workflows/ci.yml) et lors d'un test manuel sur Mac réel.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VERSION="3.0.0"
DMG_NAME="Bobine-${VERSION}.dmg"

echo "=== [1/5] Vérification de l'environnement ==="
if [ "$(uname -s)" != "Darwin" ]; then
    echo "Erreur: ce script doit tourner sur macOS (PyInstaller ne cross-compile pas)." >&2
    exit 1
fi
if ! command -v hdiutil >/dev/null 2>&1; then
    echo "Erreur: hdiutil est requis (outil natif macOS)." >&2
    exit 1
fi

PYTHON_BIN="${REPO_DIR}/backend/.venv/bin/python"
PYINSTALLER_BIN="${REPO_DIR}/backend/.venv/bin/pyinstaller"
if [ ! -x "${PYINSTALLER_BIN}" ]; then
    if command -v pyinstaller >/dev/null 2>&1; then
        PYINSTALLER_BIN="$(command -v pyinstaller)"
    else
        echo "Erreur: pyinstaller est introuvable." >&2
        exit 1
    fi
fi

echo "=== [2/5] Vérification / Build du frontend Next.js ==="
if [ ! -d "${REPO_DIR}/frontend/out" ]; then
    echo "Construction du frontend Next.js (export statique)..."
    (cd "${REPO_DIR}/frontend" && npm ci && npm run build)
fi

echo "=== [3/5] Compilation PyInstaller (Bobine.app) ==="
(cd "${REPO_DIR}/backend" && "${PYINSTALLER_BIN}" --noconfirm "${SCRIPT_DIR}/bobine.spec")

APP_PATH="${REPO_DIR}/backend/dist/Bobine.app"
if [ ! -d "${APP_PATH}" ]; then
    echo "Erreur: la compilation PyInstaller n'a pas produit ${APP_PATH}" >&2
    exit 1
fi

echo "=== [4/5] Signature ad-hoc (requise par le noyau sur Apple Silicon, cf. plan §4) ==="
# Sans ceci, macOS tue au lancement ("Killed: 9") tout binaire/bibliothèque
# non signé sur Apple Silicon — l'exigence vient du noyau (AMFI), pas de
# Gatekeeper : cette signature ad-hoc ("-s -") ne remplace PAS une vraie
# signature développeur et ne supprime PAS l'avertissement "éditeur non
# identifié" à l'ouverture (limitation connue et assumée, décision #7 du
# CDC — pas de certificat de signature de code pour l'instant).
codesign --force --deep -s - "${APP_PATH}"

echo "=== [5/5] Création du .dmg via hdiutil ==="
OUTPUT_DIR="${REPO_DIR}/dist-dmg"
STAGING_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGING_DIR}"' EXIT

cp -R "${APP_PATH}" "${STAGING_DIR}/"
ln -s /Applications "${STAGING_DIR}/Applications"

mkdir -p "${OUTPUT_DIR}"
hdiutil create -volname "Bobine" -srcfolder "${STAGING_DIR}" -ov -format UDZO "${OUTPUT_DIR}/${DMG_NAME}"

echo ""
echo " Image disque macOS générée avec succès :"
echo "  Fichier : ${OUTPUT_DIR}/${DMG_NAME}"
echo "  Taille  : $(du -h "${OUTPUT_DIR}/${DMG_NAME}" | cut -f1)"

#!/usr/bin/env bash
# ==============================================================================
# Script de construction de Bobine.app + Bobine.dmg (macOS)
#
# NE PEUT ÊTRE EXÉCUTÉ QUE SUR UNE VRAIE MACHINE macOS — PyInstaller ne
# cross-compile pas (aucun bundle macOS ne peut être produit depuis Linux ou
# Windows). Exécuté par le job CI `macos-build` (.github/workflows/ci.yml) à
# chaque push ; aucune validation sur un Mac réel n'est consignée à ce jour.
# Écrit d'après la documentation PyInstaller/Apple. Le `.dmg` produit n'embarque
# ni ffmpeg ni ffprobe (voir `backend/app/utils/ffmpeg_binaries.py`).
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source de vérité unique : fichier
# VERSION à la racine du dépôt — c'est aussi ce qui finit bundlé dans
# Bobine.app (cf. bobine.spec) et lu au runtime par app.utils.version.
VERSION="${VERSION:-$(cat "${REPO_DIR}/VERSION")}"

# Version utilisée dans le NOM DU FICHIER .dmg — délibérément distincte de
# VERSION : par défaut identique (builds
# stables), mais la CI passe la valeur fixe "beta" ou "canary" selon le
# canal rolling concerné — un seul nom de fichier stable dans le temps par
# canal plutôt qu'un nouveau nom à chaque reconstruction.
DMG_FILENAME_VERSION="${DMG_FILENAME_VERSION:-$VERSION}"
DMG_NAME="Bobine-${DMG_FILENAME_VERSION}.dmg"

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

echo "=== [3b/5] Fenêtre native du projecteur ==="
# Remplace le navigateur piloté sur macOS : Safari n'a ni kiosque ni choix de
# l'écran. Copiée dans le bundle AVANT la signature ad-hoc ci-dessous.
if command -v cargo >/dev/null 2>&1; then
    (cd "${REPO_DIR}/projector" && cargo build --release)
    cp "${REPO_DIR}/projector/target/release/bobine-projector" "${APP_PATH}/Contents/MacOS/bobine-projector"
else
    echo "Avertissement: cargo introuvable — le projecteur utilisera le navigateur par défaut." >&2
fi

echo "=== [3c/5] Sidecar des périphériques (audio, Bluetooth, Wi-Fi) ==="
# Copié dans le bundle AVANT la signature ad-hoc ; sans lui, l'onglet Périphériques reste « non pris en charge ».
if command -v cargo >/dev/null 2>&1; then
    (cd "${REPO_DIR}/devices" && cargo build --release --locked)
    cp "${REPO_DIR}/devices/target/release/bobine-devices" "${APP_PATH}/Contents/MacOS/bobine-devices"
else
    echo "Avertissement: cargo introuvable — l'onglet Périphériques sera indisponible." >&2
fi

echo "=== [3d/5] Composant audio natif (facultatif) ==="
# Copié dans le bundle AVANT la signature ad-hoc ; absent, la lecture des tags passe par ffprobe/ffmpeg.
if command -v cargo >/dev/null 2>&1; then
    (cd "${REPO_DIR}/media" && cargo build --release --locked)
    cp "${REPO_DIR}/media/target/release/bobine-media" "${APP_PATH}/Contents/MacOS/bobine-media"
else
    echo "Avertissement: cargo introuvable — bundle sans composant audio natif." >&2
fi

echo "=== [4/5] Signature ad-hoc (requise par le noyau sur Apple Silicon) ==="
# Sans ceci, macOS tue au lancement ("Killed: 9") tout binaire/bibliothèque
# non signé sur Apple Silicon — l'exigence vient du noyau (AMFI), pas de
# Gatekeeper : cette signature ad-hoc ("-s -") ne remplace PAS une vraie
# signature développeur et ne supprime PAS l'avertissement "éditeur non
# identifié" à l'ouverture (limitation connue et assumée : pas de
# certificat de signature de code pour l'instant).
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

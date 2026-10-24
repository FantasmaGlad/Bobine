#!/usr/bin/env bash
# Vérifie (ou, avec BOBINE_BUILD_DIST=1, construit) l'arbre PyInstaller dist/Bobine
# consommé par les paquets RPM et Arch. En CI l'arbre vient de l'artefact des jobs .deb
# (même binaire) ; en local il se construit comme dans build_deb.sh (étapes 2 et 3).
#
# Usage : ensure_dist.sh   (affiche le chemin de l'arbre sur la dernière ligne de stdout)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DIST_DIR="${BOBINE_DIST_DIR:-${REPO_DIR}/backend/dist/Bobine}"

if [ ! -f "${DIST_DIR}/BobineBackend" ] || [ ! -f "${DIST_DIR}/BobineTray" ]; then
    if [ "${BOBINE_BUILD_DIST:-0}" != "1" ]; then
        echo "Erreur: arbre PyInstaller introuvable dans ${DIST_DIR}." >&2
        echo "  - fournir BOBINE_DIST_DIR (arbre dist/Bobine, p. ex. extrait de l'artefact CI bobine-dist-linux-<arch>),"  >&2
        echo "  - ou lancer avec BOBINE_BUILD_DIST=1 pour le construire ici (frontend + PyInstaller)." >&2
        exit 1
    fi
    PYTHON_BIN="${REPO_DIR}/backend/.venv/bin/python"
    if [ -x "${PYTHON_BIN}" ]; then
        PYINSTALLER_CMD=("${PYTHON_BIN}" -m PyInstaller)
    elif command -v pyinstaller >/dev/null 2>&1; then
        PYINSTALLER_CMD=("$(command -v pyinstaller)")
    else
        echo "Erreur: pyinstaller est introuvable." >&2
        exit 1
    fi
    if [ ! -d "${REPO_DIR}/frontend/out" ]; then
        (cd "${REPO_DIR}/frontend" && npm run build) >&2
    fi
    (cd "${REPO_DIR}/backend" && "${PYINSTALLER_CMD[@]}" --noconfirm "${REPO_DIR}/packaging/linux/bobine.spec") >&2
    DIST_DIR="${REPO_DIR}/backend/dist/Bobine"
    MEDIA_BINARY="${BOBINE_MEDIA_BINARY:-${REPO_DIR}/media/target/release/bobine-media}"
    if [ -x "${MEDIA_BINARY}" ]; then
        cp "${MEDIA_BINARY}" "${DIST_DIR}/bobine-media"
        chmod 0755 "${DIST_DIR}/bobine-media"
    fi
fi
echo "${DIST_DIR}"

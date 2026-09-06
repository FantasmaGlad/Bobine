#!/usr/bin/env bash
# ==============================================================================
# Script de construction du paquet Debian (.deb) de Bobine
# PortabiliteCrossPlatformX — Lot 2 (Linux non-headless)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VERSION="2.0.1"
PKG_NAME="bobine"
ARCH="amd64"
DEB_NAME="${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "=== [1/5] Vérification de l'environnement ==="
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Erreur: dpkg-deb est requis pour construire le paquet .deb." >&2
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

echo "=== [3/5] Compilation PyInstaller (BobineBackend + BobineTray) ==="
(cd "${REPO_DIR}/backend" && "${PYINSTALLER_BIN}" --noconfirm "${SCRIPT_DIR}/bobine.spec")

DIST_DIR="${REPO_DIR}/backend/dist/Bobine"
if [ ! -f "${DIST_DIR}/BobineBackend" ] || [ ! -f "${DIST_DIR}/BobineTray" ]; then
    echo "Erreur: la compilation PyInstaller n'a pas produit les exécutables attendus dans ${DIST_DIR}" >&2
    exit 1
fi

echo "=== [4/5] Assemblage de l'arborescence Debian ==="
OUTPUT_DIR="${REPO_DIR}/dist-deb"
STAGING_DIR="${OUTPUT_DIR}/bobine_${VERSION}_${ARCH}"

rm -rf "${STAGING_DIR}"
mkdir -p "${STAGING_DIR}/DEBIAN"
mkdir -p "${STAGING_DIR}/usr/lib/bobine"
mkdir -p "${STAGING_DIR}/usr/bin"
mkdir -p "${STAGING_DIR}/usr/share/applications"
mkdir -p "${STAGING_DIR}/etc/xdg/autostart"
mkdir -p "${STAGING_DIR}/usr/lib/systemd/user"
mkdir -p "${STAGING_DIR}/usr/share/pixmaps"
mkdir -p "${STAGING_DIR}/usr/share/icons"
mkdir -p "${STAGING_DIR}/usr/share/metainfo"
mkdir -p "${STAGING_DIR}/usr/share/doc/bobine"

# Copie des binaires et assets de l'application
cp -a "${DIST_DIR}/"* "${STAGING_DIR}/usr/lib/bobine/"

# Wrapper de lancement dans /usr/bin
cat << 'EOF' > "${STAGING_DIR}/usr/bin/bobine"
#!/bin/sh
exec /usr/lib/bobine/BobineTray "$@"
EOF
chmod 0755 "${STAGING_DIR}/usr/bin/bobine"

# Fichiers .desktop et autostart (avec alias com.bobine.app pour AppStream)
cp "${SCRIPT_DIR}/bobine.desktop" "${STAGING_DIR}/usr/share/applications/bobine.desktop"
cp "${SCRIPT_DIR}/bobine.desktop" "${STAGING_DIR}/usr/share/applications/com.bobine.app.desktop"
cp "${SCRIPT_DIR}/bobine.desktop" "${STAGING_DIR}/etc/xdg/autostart/bobine.desktop"

# Métadonnées AppStream (pour le Centre d'applications Ubuntu, GNOME Software, Discover)
cp "${SCRIPT_DIR}/bobine.metainfo.xml" "${STAGING_DIR}/usr/share/metainfo/com.bobine.app.metainfo.xml"
cp "${SCRIPT_DIR}/bobine.metainfo.xml" "${STAGING_DIR}/usr/share/metainfo/bobine.metainfo.xml"

# Informations de Licence / Copyright Debian standard
cp "${SCRIPT_DIR}/copyright" "${STAGING_DIR}/usr/share/doc/bobine/copyright"

# Service systemd utilisateur
cp "${SCRIPT_DIR}/bobine.service" "${STAGING_DIR}/usr/lib/systemd/user/bobine.service"

# Icônes de l'application (multi-résolution hicolor + fallback pixmaps)
ICONS_SRC="${SCRIPT_DIR}/icons"
if [ ! -d "${ICONS_SRC}/hicolor" ] && [ -f "${REPO_DIR}/scripts/generate_platform_icons.py" ]; then
    "${PYTHON_BIN}" "${REPO_DIR}/scripts/generate_platform_icons.py" || true
fi

if [ -d "${ICONS_SRC}/hicolor" ]; then
    cp -a "${ICONS_SRC}/hicolor" "${STAGING_DIR}/usr/share/icons/"
fi
if [ -f "${ICONS_SRC}/pixmaps/bobine.png" ]; then
    cp "${ICONS_SRC}/pixmaps/bobine.png" "${STAGING_DIR}/usr/share/pixmaps/bobine.png"
    cp "${ICONS_SRC}/pixmaps/com.bobine.app.png" "${STAGING_DIR}/usr/share/pixmaps/com.bobine.app.png" 2>/dev/null || true
elif [ -f "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" ]; then
    cp "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" "${STAGING_DIR}/usr/share/pixmaps/bobine.png"
    cp "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" "${STAGING_DIR}/usr/share/pixmaps/com.bobine.app.png"
fi

# Métadonnées et scripts de maintenance Debian
cp "${SCRIPT_DIR}/DEBIAN/control" "${STAGING_DIR}/DEBIAN/control"
cp "${SCRIPT_DIR}/DEBIAN/postinst" "${STAGING_DIR}/DEBIAN/postinst"
cp "${SCRIPT_DIR}/DEBIAN/prerm" "${STAGING_DIR}/DEBIAN/prerm"
cp "${SCRIPT_DIR}/DEBIAN/postrm" "${STAGING_DIR}/DEBIAN/postrm"

chmod 0755 "${STAGING_DIR}/DEBIAN/postinst"
chmod 0755 "${STAGING_DIR}/DEBIAN/prerm"
chmod 0755 "${STAGING_DIR}/DEBIAN/postrm"
chmod 0644 "${STAGING_DIR}/DEBIAN/control"

# Normalisation des permissions dans le paquet
find "${STAGING_DIR}" -type d -exec chmod 0755 {} +
find "${STAGING_DIR}/usr/share" -type f -exec chmod 0644 {} +
chmod 0755 "${STAGING_DIR}/usr/lib/bobine/BobineBackend"
chmod 0755 "${STAGING_DIR}/usr/lib/bobine/BobineTray"

echo "=== [5/5] Création du paquet .deb via dpkg-deb ==="
mkdir -p "${OUTPUT_DIR}"
dpkg-deb --build --root-owner-group "${STAGING_DIR}" "${OUTPUT_DIR}/${DEB_NAME}"

echo ""
echo " Paquet Debian généré avec succès :"
echo "  Fichier : ${OUTPUT_DIR}/${DEB_NAME}"
echo "  Taille  : $(du -h "${OUTPUT_DIR}/${DEB_NAME}" | cut -f1)"
echo ""
dpkg-deb -I "${OUTPUT_DIR}/${DEB_NAME}"

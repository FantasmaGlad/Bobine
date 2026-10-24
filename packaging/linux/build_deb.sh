#!/usr/bin/env bash
# ==============================================================================
# Script de construction du paquet Debian (.deb) de Bobine
# Linux non-headless (profil bureau)
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source de vérité unique : fichier
# VERSION à la racine du dépôt. Surchargeable via l'environnement (CI passe
# une valeur au format Debian, ex. "5.0.2+beta.41" ou "5.0.2+canary.42" selon
# le canal — le '+' trie APRÈS la version de base et le compteur croît à chaque
# build, cf. dpkg --compare-versions).
# C'est ce qui va dans le champ Version: du paquet (DEBIAN/control
# ci-dessous), lu par dpkg/apt — jamais dans le nom de fichier (cf.
# DEB_FILENAME_VERSION).
VERSION="${VERSION:-$(cat "${REPO_DIR}/VERSION")}"

# Version utilisée dans le NOM DU FICHIER .deb — délibérément distincte de
# VERSION ci-dessus : GitHub Releases
# réécrit silencieusement le caractère '~' en '.' dans les noms d'assets
# téléchargés (constaté en pratique), ce qui casserait la convention Debian
# du nom de fichier pour toute version contenant un '~'. Par défaut identique
# à VERSION (paquets stables, sans '~') ; la CI passe la valeur fixe "beta"
# ou "canary" selon le canal rolling concerné — un seul nom de fichier stable
# dans le temps par canal, jamais de caractère problématique, et aucune
# accumulation de fichiers versionnés à chaque reconstruction.
DEB_FILENAME_VERSION="${DEB_FILENAME_VERSION:-$VERSION}"
PKG_NAME="bobine"
ARCH="${ARCH:-$(dpkg --print-architecture)}"
DEB_NAME="${PKG_NAME}_${DEB_FILENAME_VERSION}_${ARCH}.deb"

echo "=== [1/5] Vérification de l'environnement ==="
if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "Erreur: dpkg-deb est requis pour construire le paquet .deb." >&2
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

echo "=== [2/5] Vérification / Build du frontend Next.js ==="
if [ ! -d "${REPO_DIR}/frontend/out" ]; then
    echo "Construction du frontend Next.js (export statique)..."
    (cd "${REPO_DIR}/frontend" && npm run build)
fi

echo "=== [3/5] Compilation PyInstaller (BobineBackend + BobineTray) ==="
(cd "${REPO_DIR}/backend" && "${PYINSTALLER_CMD[@]}" --noconfirm "${SCRIPT_DIR}/bobine.spec")

DIST_DIR="${REPO_DIR}/backend/dist/Bobine"
if [ ! -f "${DIST_DIR}/BobineBackend" ] || [ ! -f "${DIST_DIR}/BobineTray" ]; then
    echo "Erreur: la compilation PyInstaller n'a pas produit les exécutables attendus dans ${DIST_DIR}" >&2
    exit 1
fi

# Composant audio natif (facultatif) : lu par BobineBackend à côté de son exécutable. Compilé en
# amont (scripts/ci/stage-media.py) ; absent, le paquet reste complet et fonctionnel : la
# lecture des tags et des pochettes passe alors par ffprobe/ffmpeg.
MEDIA_BINARY="${BOBINE_MEDIA_BINARY:-${REPO_DIR}/media/target/release/bobine-media}"
if [ -x "${MEDIA_BINARY}" ]; then
    cp "${MEDIA_BINARY}" "${DIST_DIR}/bobine-media"
    chmod 0755 "${DIST_DIR}/bobine-media"
    echo "Composant audio natif inclus : ${MEDIA_BINARY}"
else
    echo "Composant audio natif absent : paquet sans bobine-media (repli ffprobe/ffmpeg)." >&2
fi

python3 "${REPO_DIR}/packaging/common/sanitize_elf.py" "${DIST_DIR}"

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
mkdir -p "${STAGING_DIR}/usr/share/appdata"
mkdir -p "${STAGING_DIR}/usr/share/doc/bobine"

mkdir -p "${STAGING_DIR}/usr/share/bobine"
cp "${REPO_DIR}/packaging/storage/49-bobine-storage.rules.in" "${STAGING_DIR}/usr/share/bobine/"
cp "${REPO_DIR}/packaging/storage/configure-storage-access" "${STAGING_DIR}/usr/lib/bobine/"
chmod 0755 "${STAGING_DIR}/usr/lib/bobine/configure-storage-access"

# Copie des binaires et assets de l'application
cp -a "${DIST_DIR}/"* "${STAGING_DIR}/usr/lib/bobine/"

# Wrapper de lancement dans /usr/bin
cat << 'EOF' > "${STAGING_DIR}/usr/bin/bobine"
#!/bin/sh
exec /usr/lib/bobine/BobineTray "$@"
EOF
chmod 0755 "${STAGING_DIR}/usr/bin/bobine"

# Fichier .desktop unique (com.bobine.app.desktop pour conformité AppStream et éviter les doublons dans GNOME)
cp "${SCRIPT_DIR}/bobine.desktop" "${STAGING_DIR}/usr/share/applications/com.bobine.app.desktop"
cp "${SCRIPT_DIR}/bobine.desktop" "${STAGING_DIR}/etc/xdg/autostart/com.bobine.app.desktop"

# Métadonnées AppStream (pour le Centre d'applications Ubuntu, GNOME Software, Discover).
# Le journal des versions reçoit l'entrée de la version construite si elle n'y figure pas encore.
APPSTREAM_TMP="$(mktemp)"
cp "${SCRIPT_DIR}/bobine.metainfo.xml" "${APPSTREAM_TMP}"
APPSTREAM_VERSION="${VERSION//[~+]/-}"
if ! grep -q "<release version=\"${APPSTREAM_VERSION}\"" "${APPSTREAM_TMP}"; then
    sed -i "s|<releases>|<releases>\n    <release version=\"${APPSTREAM_VERSION}\" date=\"$(date -u +%F)\"/>|" "${APPSTREAM_TMP}"
fi
cp "${APPSTREAM_TMP}" "${STAGING_DIR}/usr/share/metainfo/com.bobine.app.metainfo.xml"
cp "${APPSTREAM_TMP}" "${STAGING_DIR}/usr/share/appdata/com.bobine.app.appdata.xml"
rm -f "${APPSTREAM_TMP}"

# Informations de Licence / Copyright Debian standard
cp "${SCRIPT_DIR}/copyright" "${STAGING_DIR}/usr/share/doc/bobine/copyright"

# Service systemd utilisateur
cp "${SCRIPT_DIR}/bobine.service" "${STAGING_DIR}/usr/lib/systemd/user/bobine.service"

# Icônes de l'application (multi-résolution hicolor + fallback pixmaps)
ICONS_SRC="${SCRIPT_DIR}/icons"
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

# Injection dynamique du numéro de version : DEBIAN/control ne porte plus qu'un placeholder "0.0.0" versionné
# dans le dépôt — remplacé ici par VERSION, jamais figé en dur comme avant
# (le paquet publié s'annonçait "3.0.0" quelle que soit la version réelle,
# cf. `dpkg -I` sur un ancien paquet).
sed -i "s/^Version:.*/Version: ${VERSION}/" "${STAGING_DIR}/DEBIAN/control"
sed -i "s/^Architecture:.*/Architecture: ${ARCH}/" "${STAGING_DIR}/DEBIAN/control"

# Calcul dynamique de la taille installée pour le Centre d'applications
INSTALLED_SIZE=$(du -sk "${STAGING_DIR}/usr" | awk '{print $1}')
if ! grep -q "^Installed-Size:" "${STAGING_DIR}/DEBIAN/control"; then
    echo "Installed-Size: ${INSTALLED_SIZE}" >> "${STAGING_DIR}/DEBIAN/control"
else
    sed -i "s/^Installed-Size:.*/Installed-Size: ${INSTALLED_SIZE}/" "${STAGING_DIR}/DEBIAN/control"
fi

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

#!/usr/bin/env bash
# ==============================================================================
# Assemble l'arborescence FHS de Bobine (profil bureau Linux) à partir de l'arbre
# PyInstaller déjà construit. Partagé par les paquets RPM et Arch : même contenu
# que le .deb (cf. packaging/linux/build_deb.sh, étape 4), sans scripts de
# maintenance (propres à chaque gestionnaire de paquets).
#
# Usage : stage_root.sh <dossier PyInstaller dist/Bobine> <dossier destination> [version]
#   <version> : version annoncée dans le journal AppStream (défaut : fichier VERSION).
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LINUX_DIR="${REPO_DIR}/packaging/linux"

DIST_DIR="${1:?dossier PyInstaller (dist/Bobine)}"
DEST="${2:?dossier de destination}"
VERSION="${3:-$(cat "${REPO_DIR}/VERSION")}"

for exe in BobineBackend BobineTray; do
    if [ ! -f "${DIST_DIR}/${exe}" ]; then
        echo "Erreur: ${DIST_DIR}/${exe} introuvable (arbre PyInstaller incomplet)." >&2
        exit 1
    fi
done

rm -rf "${DEST}"
mkdir -p "${DEST}/usr/lib/bobine" "${DEST}/usr/bin" "${DEST}/usr/share/applications" \
         "${DEST}/etc/xdg/autostart" "${DEST}/usr/lib/systemd/user" "${DEST}/usr/share/pixmaps" \
         "${DEST}/usr/share/icons" "${DEST}/usr/share/metainfo" \
         "${DEST}/usr/share/doc/bobine"

cp -a "${DIST_DIR}/." "${DEST}/usr/lib/bobine/"
python3 "${SCRIPT_DIR}/sanitize_elf.py" "${DEST}/usr/lib/bobine"
mkdir -p "${DEST}/usr/share/bobine"
cp "${REPO_DIR}/packaging/storage/49-bobine-storage.rules.in" "${DEST}/usr/share/bobine/"
cp "${REPO_DIR}/packaging/storage/configure-storage-access" "${DEST}/usr/lib/bobine/"
chmod 0755 "${DEST}/usr/lib/bobine/configure-storage-access"

cat > "${DEST}/usr/bin/bobine" <<'WRAP'
#!/bin/sh
exec /usr/lib/bobine/BobineTray "$@"
WRAP
chmod 0755 "${DEST}/usr/bin/bobine"

cp "${LINUX_DIR}/bobine.desktop" "${DEST}/usr/share/applications/com.bobine.app.desktop"
cp "${LINUX_DIR}/bobine.desktop" "${DEST}/etc/xdg/autostart/com.bobine.app.desktop"

# AppStream : même ajout de l'entrée de version que build_deb.sh. Le doublon au chemin
# historique /usr/share/appdata (ancien format, déprécié) n'est pas reproduit ici.
APPSTREAM_TMP="$(mktemp)"
cp "${LINUX_DIR}/bobine.metainfo.xml" "${APPSTREAM_TMP}"
APPSTREAM_VERSION="${VERSION//[~+]/-}"
if ! grep -q "<release version=\"${APPSTREAM_VERSION}\"" "${APPSTREAM_TMP}"; then
    sed -i "s|<releases>|<releases>\n    <release version=\"${APPSTREAM_VERSION}\" date=\"$(date -u +%F)\"/>|" "${APPSTREAM_TMP}"
fi
cp "${APPSTREAM_TMP}" "${DEST}/usr/share/metainfo/com.bobine.app.metainfo.xml"
rm -f "${APPSTREAM_TMP}"

cp "${LINUX_DIR}/copyright" "${DEST}/usr/share/doc/bobine/copyright"
cp "${LINUX_DIR}/bobine.service" "${DEST}/usr/lib/systemd/user/bobine.service"

ICONS_SRC="${LINUX_DIR}/icons"
if [ -d "${ICONS_SRC}/hicolor" ]; then
    cp -a "${ICONS_SRC}/hicolor" "${DEST}/usr/share/icons/"
fi
if [ -f "${ICONS_SRC}/pixmaps/bobine.png" ]; then
    cp "${ICONS_SRC}/pixmaps/bobine.png" "${DEST}/usr/share/pixmaps/bobine.png"
    cp "${ICONS_SRC}/pixmaps/com.bobine.app.png" "${DEST}/usr/share/pixmaps/com.bobine.app.png" 2>/dev/null || true
elif [ -f "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" ]; then
    cp "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" "${DEST}/usr/share/pixmaps/bobine.png"
    cp "${REPO_DIR}/Assets/Images/logo_bobine_icon.png" "${DEST}/usr/share/pixmaps/com.bobine.app.png"
fi

# Permissions : mêmes règles que le .deb.
find "${DEST}" -type d -exec chmod 0755 {} +
find "${DEST}/usr/share" "${DEST}/etc" -type f -exec chmod 0644 {} +
chmod 0644 "${DEST}/usr/lib/systemd/user/bobine.service"
chmod 0755 "${DEST}/usr/lib/bobine/BobineBackend" "${DEST}/usr/lib/bobine/BobineTray"
[ -f "${DEST}/usr/lib/bobine/bobine-media" ] && chmod 0755 "${DEST}/usr/lib/bobine/bobine-media"
exit 0

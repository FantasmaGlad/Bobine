#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
COMMON_DIR="${REPO_DIR}/packaging/common"
# shellcheck source=packaging/common/glibc_floor.sh
source "${COMMON_DIR}/glibc_floor.sh"

VERSION="${VERSION:-$(cat "${REPO_DIR}/VERSION")}"
ARCH="${ARCH:-$(dpkg --print-architecture)}"
DEB_NAME="bobine_${DEB_FILENAME_VERSION:-$VERSION}_${ARCH}.deb"
OUTPUT_DIR="${REPO_DIR}/dist-deb"
STAGING_DIR="${OUTPUT_DIR}/bobine_${VERSION}_${ARCH}"

echo "=== [1/4] Vérification de l'environnement ==="
command -v dpkg-deb >/dev/null 2>&1 || { echo "Erreur: dpkg-deb est requis pour construire le paquet .deb." >&2; exit 1; }
DIST_DIR="$(BOBINE_BUILD_DIST="${BOBINE_BUILD_DIST:-1}" "${COMMON_DIR}/ensure_dist.sh" | tail -n1)"

echo "=== [2/4] Assemblage de l'arborescence ==="
"${COMMON_DIR}/stage_root.sh" "${DIST_DIR}" "${STAGING_DIR}" "${VERSION}"
install -D -m 0644 "${STAGING_DIR}/usr/share/metainfo/com.bobine.app.metainfo.xml" "${STAGING_DIR}/usr/share/appdata/com.bobine.app.appdata.xml"

echo "=== [3/4] Métadonnées Debian ==="
install -d -m 0755 "${STAGING_DIR}/DEBIAN"
install -m 0644 "${SCRIPT_DIR}/DEBIAN/control" "${STAGING_DIR}/DEBIAN/control"
for script in postinst prerm postrm; do
    install -m 0755 "${SCRIPT_DIR}/DEBIAN/${script}" "${STAGING_DIR}/DEBIAN/${script}"
done
CONTROL="${STAGING_DIR}/DEBIAN/control"
sed -i "s/^Version:.*/Version: ${VERSION}/; s/^Architecture:.*/Architecture: ${ARCH}/" "${CONTROL}"
GLIBC_MIN="$(bobine_glibc_check "${DIST_DIR}")"
bobine_deb_require_glibc "${CONTROL}" "${GLIBC_MIN}"
echo "Dépendance libc6 (>= ${GLIBC_MIN}) ajoutée au paquet."
sed -i '/^Installed-Size:/d' "${CONTROL}"
echo "Installed-Size: $(du -sk "${STAGING_DIR}/usr" | awk '{print $1}')" >> "${CONTROL}"

echo "=== [4/4] dpkg-deb ==="
dpkg-deb --build --root-owner-group "${STAGING_DIR}" "${OUTPUT_DIR}/${DEB_NAME}"
echo " Paquet Debian généré : ${OUTPUT_DIR}/${DEB_NAME} ($(du -h "${OUTPUT_DIR}/${DEB_NAME}" | cut -f1))"
dpkg-deb -I "${OUTPUT_DIR}/${DEB_NAME}"

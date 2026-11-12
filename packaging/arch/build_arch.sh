#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../common/version.sh
source "${SCRIPT_DIR}/../common/version.sh"

if [ "$(id -u)" -eq 0 ]; then
    id builder >/dev/null 2>&1 || useradd -m builder
    OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/dist-arch}"
    mkdir -p "${OUTPUT_DIR}"; chmod 0777 "${OUTPUT_DIR}"
    exec runuser -u builder -- env "OUTPUT_DIR=${OUTPUT_DIR}" "PATH=${PATH}" \
        ${VERSION:+"VERSION=${VERSION}"} ${PKG_FILENAME_VERSION:+"PKG_FILENAME_VERSION=${PKG_FILENAME_VERSION}"} \
        ${PKG_ARCH:+"PKG_ARCH=${PKG_ARCH}"} ${BOBINE_DIST_DIR:+"BOBINE_DIST_DIR=${BOBINE_DIST_DIR}"} ${BOBINE_BUILD_DIST:+"BOBINE_BUILD_DIST=${BOBINE_BUILD_DIST}"} \
        "${BASH_SOURCE[0]}" "$@"
fi

VERSION="${VERSION:-$(cat "${REPO_DIR}/VERSION")}"
PKG_ARCH="${PKG_ARCH:-$(uname -m)}"
case "${PKG_ARCH}" in
    x86_64|aarch64) ;;
    arm64) PKG_ARCH=aarch64 ;;
    amd64) PKG_ARCH=x86_64 ;;
    *) echo "Erreur: architecture non prise en charge : ${PKG_ARCH}" >&2; exit 1 ;;
esac
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/dist-arch}"
split_bobine_version "${VERSION}"
PKGREL="1"

echo "=== [1/4] Vérification de l'environnement ==="
command -v makepkg >/dev/null 2>&1 || { echo "Erreur: makepkg est requis (Arch Linux : pacman -S base-devel)." >&2; exit 1; }
DIST_DIR="$("${SCRIPT_DIR}/../common/ensure_dist.sh" | tail -n1)"

echo "=== [2/4] Assemblage de l'arborescence ==="
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
"${SCRIPT_DIR}/../common/stage_root.sh" "${DIST_DIR}" "${WORK}/root" "${VERSION}"
mkdir -p "${WORK}/pkg"
tar --owner=0 --group=0 --numeric-owner -cf "${WORK}/pkg/bobine-root.tar" -C "${WORK}/root" .
cp "${SCRIPT_DIR}/PKGBUILD" "${SCRIPT_DIR}/bobine.install" "${WORK}/pkg/"

echo "=== [3/4] makepkg (${PKG_ARCH}) ==="
MAKEPKG_CONF="${WORK}/makepkg.conf"
cp /etc/makepkg.conf "${MAKEPKG_CONF}"
{
    echo "CARCH=\"${PKG_ARCH}\""
    echo "PKGDEST=\"${WORK}/out\""
    echo "PKGEXT='.pkg.tar.zst'"
    echo "PACKAGER=\"${PACKAGER:-FantasmaGlad <193235053+FantasmaGlad@users.noreply.github.com>}\""
} >> "${MAKEPKG_CONF}"
mkdir -p "${WORK}/out"
(
    cd "${WORK}/pkg"
    BOBINE_PKGVER="${ARCH_VERSION}" BOBINE_PKGREL="${PKGREL}" \
        makepkg --config "${MAKEPKG_CONF}" --nodeps --noconfirm --force
)

echo "=== [4/4] Nommage de l'asset ==="
BUILT="$(ls "${WORK}"/out/bobine-*.pkg.tar.zst | head -n1)"
mkdir -p "${OUTPUT_DIR}"
if [ -n "${PKG_FILENAME_VERSION:-}" ] && [ "${PKG_FILENAME_VERSION}" != "${VERSION}" ]; then
    PKG_NAME="bobine-${PKG_FILENAME_VERSION}-${PKG_ARCH}.pkg.tar.zst"
else
    PKG_NAME="$(basename "${BUILT}")"
fi
cp "${BUILT}" "${OUTPUT_DIR}/${PKG_NAME}"
echo ""
echo " Paquet Arch généré : ${OUTPUT_DIR}/${PKG_NAME} ($(du -h "${OUTPUT_DIR}/${PKG_NAME}" | cut -f1))"

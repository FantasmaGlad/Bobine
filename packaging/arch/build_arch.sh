#!/usr/bin/env bash
# ==============================================================================
# Construit le paquet Arch (.pkg.tar.zst) de Bobine à partir de l'arbre PyInstaller —
# le même que celui du .deb. Aucune compilation : makepkg ne fait qu'emballer.
#
# Environnement :
#   VERSION                version de build (défaut : fichier VERSION), p. ex. 5.0.6~0.canary.42
#   PKG_FILENAME_VERSION   "beta"/"canary" => bobine-<canal>-<arch>.pkg.tar.zst ; vide => nom natif
#   PKG_ARCH               architecture du paquet : x86_64 ou aarch64 (défaut : uname -m). Un paquet
#                          aarch64 peut être assemblé sur x86_64 (aucun code n'est exécuté) à partir
#                          de l'arbre construit nativement sur arm64 : makepkg reçoit CARCH=aarch64.
#   BOBINE_DIST_DIR        arbre PyInstaller (défaut backend/dist/Bobine) ; BOBINE_BUILD_DIST=1 le construit
#   OUTPUT_DIR             dossier de sortie (défaut dist-arch/)
# Dépendances : makepkg (pacman, base-devel : fakeroot, bsdtar, zstd). makepkg refuse root : si le
# script est lancé en root, il se relance sous l'utilisateur "builder" (créé au besoin).
# ==============================================================================
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
# Configuration makepkg dédiée : CARCH forcé à l'architecture visée, paquets déposés dans pkgdest.
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

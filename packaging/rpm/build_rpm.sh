#!/usr/bin/env bash
# ==============================================================================
# Construit le paquet RPM de Bobine (Fedora et dérivés) pour l'architecture courante
# (x86_64 ou aarch64) à partir de l'arbre PyInstaller — le même que celui du .deb.
#
# Environnement :
#   VERSION               version de build (défaut : fichier VERSION), p. ex. 5.0.5+canary.42
#   RPM_FILENAME_VERSION  suffixe du fichier produit : "beta"/"canary" => bobine-<canal>.<arch>.rpm ;
#                         vide => nom RPM natif (stable : bobine-<V>-1.<arch>.rpm)
#   BOBINE_DIST_DIR       arbre PyInstaller (défaut backend/dist/Bobine) ; BOBINE_BUILD_DIST=1 le construit
#   RPM_ARCH              architecture cible (défaut : uname -m)
#   OUTPUT_DIR            dossier de sortie (défaut dist-rpm/)
# Dépendances : rpm-build, tar, grep (sur Fedora : dnf install rpm-build).
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=../common/version.sh
source "${SCRIPT_DIR}/../common/version.sh"

VERSION="${VERSION:-$(cat "${REPO_DIR}/VERSION")}"
RPM_ARCH="${RPM_ARCH:-$(uname -m)}"
case "${RPM_ARCH}" in
    x86_64|aarch64) ;;
    arm64) RPM_ARCH=aarch64 ;;
    amd64) RPM_ARCH=x86_64 ;;
    *) echo "Erreur: architecture non prise en charge : ${RPM_ARCH}" >&2; exit 1 ;;
esac
OUTPUT_DIR="${OUTPUT_DIR:-${REPO_DIR}/dist-rpm}"
split_bobine_version "${VERSION}"
if [ "${CHANNEL}" = "stable" ]; then RELEASE="1"; else RELEASE="1.${CHANNEL}.${RUN}"; fi

echo "=== [1/5] Vérification de l'environnement ==="
command -v rpmbuild >/dev/null 2>&1 || { echo "Erreur: rpmbuild est requis (dnf install rpm-build)." >&2; exit 1; }
DIST_DIR="$("${SCRIPT_DIR}/../common/ensure_dist.sh" | tail -n1)"

echo "=== [2/5] Assemblage de l'arborescence ==="
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
mkdir -p "${WORK}/rpmbuild/"{SOURCES,SPECS,BUILD,RPMS,SRPMS,BUILDROOT}
"${SCRIPT_DIR}/../common/stage_root.sh" "${DIST_DIR}" "${WORK}/root" "${VERSION}"
tar --owner=0 --group=0 --numeric-owner -cf "${WORK}/rpmbuild/SOURCES/bobine-root.tar" -C "${WORK}/root" .
cp "${SCRIPT_DIR}/bobine-firewalld.xml" "${WORK}/rpmbuild/SOURCES/"
cp "${SCRIPT_DIR}/bobine.spec" "${WORK}/rpmbuild/SPECS/"

echo "=== [3/5] Version glibc minimale exigée par les binaires embarqués ==="
# Plus haut symbole GLIBC_x.y référencé par un exécutable ou une bibliothèque ELF de l'arbre.
GLIBC_MIN="$(
    find "${DIST_DIR}" -type f \( -perm -u+x -o -name '*.so*' \) -print0 \
    | xargs -0 -r grep -aoh -E 'GLIBC_[0-9]+\.[0-9]+(\.[0-9]+)?' 2>/dev/null \
    | sed 's/^GLIBC_//' | sort -uV | tail -n1
)"
GLIBC_MIN="${GLIBC_MIN:-2.17}"
echo "glibc >= ${GLIBC_MIN}"

echo "=== [4/5] rpmbuild (${RPM_ARCH}) ==="
rpmbuild -bb --target "${RPM_ARCH}" \
    --define "_topdir ${WORK}/rpmbuild" \
    --define "_buildhost build.bobine.fit" \
    --define "bobine_version ${BASE_VERSION}" \
    --define "bobine_release ${RELEASE}" \
    --define "bobine_glibc ${GLIBC_MIN}" \
    "${WORK}/rpmbuild/SPECS/bobine.spec"

echo "=== [5/5] Nommage de l'asset ==="
BUILT="$(ls "${WORK}"/rpmbuild/RPMS/*/bobine-*.rpm | head -n1)"
mkdir -p "${OUTPUT_DIR}"
if [ -n "${RPM_FILENAME_VERSION:-}" ] && [ "${RPM_FILENAME_VERSION}" != "${VERSION}" ]; then
    RPM_NAME="bobine-${RPM_FILENAME_VERSION}.${RPM_ARCH}.rpm"
else
    RPM_NAME="$(basename "${BUILT}")"
fi
cp "${BUILT}" "${OUTPUT_DIR}/${RPM_NAME}"
echo ""
echo " Paquet RPM généré : ${OUTPUT_DIR}/${RPM_NAME} ($(du -h "${OUTPUT_DIR}/${RPM_NAME}" | cut -f1))"
rpm -qip "${OUTPUT_DIR}/${RPM_NAME}" 2>/dev/null | head -n 12 || true

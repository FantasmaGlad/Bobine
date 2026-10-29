#!/usr/bin/env bash
# Emballe les mêmes binaires que le paquet Debian ; aucune recompilation par distribution.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
input="${1:?paquet Debian}"; arch="${2:?x86_64 ou aarch64}"
case "$arch" in x86_64|aarch64) ;; *) exit 2 ;; esac
. "$root/scripts/ci/container-images.sh"
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
dpkg-deb -x "$input" "$work/bundle"
export VERSION="$(dpkg-deb -f "$input" Version)"
export RPM_FILENAME_VERSION="${FILENAME_VERSION:-$VERSION}" PKG_FILENAME_VERSION="${FILENAME_VERSION:-$VERSION}"
mkdir -p "$root/dist-rpm" "$root/dist-arch"
engine="${CONTAINER_ENGINE:-docker}"
"$engine" run --rm -v "$root:/src:ro" -v "$work/bundle:/input:ro" -v "$root/dist-rpm:/output" \
    -e VERSION -e RPM_FILENAME_VERSION -e RPM_ARCH="$arch" -e BOBINE_DIST_DIR=/input/usr/lib/bobine -e OUTPUT_DIR=/output \
    "$FEDORA_IMAGE" bash -c 'dnf -y -q install rpm-build desktop-file-utils patchelf python3 && python3 /src/scripts/ci/test-package-versions.py --family rpm && /src/packaging/rpm/build_rpm.sh'
"$engine" run --rm -v "$root:/src:ro" -v "$work/bundle:/input:ro" -v "$root/dist-arch:/output" \
    -e VERSION -e PKG_FILENAME_VERSION -e PKG_ARCH="$arch" -e BOBINE_DIST_DIR=/input/usr/lib/bobine -e OUTPUT_DIR=/output \
    "$ARCH_IMAGE" bash -c 'pacman -Syu --noconfirm --needed base-devel zstd patchelf python && python /src/scripts/ci/test-package-versions.py --family arch && /src/packaging/arch/build_arch.sh'
# aarch64 : le rpm est installé et lancé par le job linux-rpm-aarch64 (Fedora arm64) ; le paquet Arch n'a pas d'image officielle (container-images.sh).
args=(); [ "$arch" = x86_64 ] || args+=(--no-install)
"$engine" run --rm -v "$root:/src:ro" -v "$root/dist-rpm:/output:ro" "$FEDORA_IMAGE" \
    bash -c 'dnf -y -q install desktop-file-utils && /src/packaging/rpm/test_rpm.sh "$1" "${2:-}"' -- "/output/$(basename "$(find "$root/dist-rpm" -name "*.$arch.rpm" | head -1)")" "${args[@]}"
"$engine" run --rm -v "$root:/src:ro" -v "$root/dist-arch:/output:ro" "$ARCH_IMAGE" \
    bash -c '/src/packaging/arch/test_arch.sh "$1" "${2:-}"' -- "/output/$(basename "$(find "$root/dist-arch" -name "*-$arch.pkg.tar.zst" | head -1)")" "${args[@]}"

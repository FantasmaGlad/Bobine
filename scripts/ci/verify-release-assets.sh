#!/usr/bin/env bash
set -euo pipefail

DIR="${1:?dossier des assets}"
S="${2:?suffixe de version (5.0.0, beta ou canary)}"

if python3 "$(dirname "$0")/../../packaging/common/channel.py" is-rolling "$S"; then
    package_version="$S"
else
    package_version="${S}-1"
fi

expected=(
    "Bobine-Setup-${S}.exe"
    "Bobine-Setup-${S}-arm64.exe"
    "bobine_${S}_amd64.deb"
    "bobine_${S}_arm64.deb"
    "bobine-${package_version}.x86_64.rpm"
    "bobine-${package_version}.aarch64.rpm"
    "bobine-${package_version}-x86_64.pkg.tar.zst"
    "bobine-${package_version}-aarch64.pkg.tar.zst"
    "bobine-${package_version}-x86_64.pkg.tar.zst.sig"
    "bobine-${package_version}-aarch64.pkg.tar.zst.sig"
    "Bobine-${S}.dmg"
    "Bobine-${S}.apk"
    "Bobine-TV-${S}.apk"
    "install.sh"
    "install.ps1"
    "SHA256SUMS"
    "SHA256SUMS.asc"
)

missing=()
for name in "${expected[@]}"; do
    path="${DIR}/${name}"
    if [[ ! -s "${path}" ]]; then
        missing+=("${name}")
    fi
done

if (( ${#missing[@]} > 0 )); then
    echo "::error::Assets de release manquants ou vides dans ${DIR} : ${missing[*]}"
    echo "Contenu réel :"
    ls -l "${DIR}"
    exit 1
fi
stray=$(cd "${DIR}" && ls -1 | grep -iE '^bobine-(assistant|deploy).*\.(exe|deb|rpm|dmg|apk)$' || true)
if [[ -n "${stray}" ]]; then
    echo "::error::paquets de Bobine Deploy dans une release de Bobine : ${stray//$'\n'/ }"
    exit 1
fi
for name in "${expected[@]}"; do
    case "${name}" in SHA256SUMS|SHA256SUMS.asc) continue ;; esac
    grep -qE "^[0-9a-f]{64}  ${name//./\\.}$" "${DIR}/SHA256SUMS" || { echo "::error::${name} absent de SHA256SUMS"; exit 1; }
done
(cd "${DIR}" && sha256sum --check --strict SHA256SUMS > /dev/null) || { echo "::error::SHA256SUMS ne correspond pas aux fichiers"; exit 1; }
echo "Tous les assets attendus (${#expected[@]}) sont présents pour '${S}'."

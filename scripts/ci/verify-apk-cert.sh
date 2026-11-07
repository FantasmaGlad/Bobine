#!/usr/bin/env bash
# Vérifie qu'une APK est signée par la clé de Bobine (empreinte SHA-256 du certificat épinglée dans
# android/signing-certificate.sha256) : `apksigner verify` seul accepte n'importe quelle signature valide, y compris
# celle d'un keystore de débogage, ce qui casserait silencieusement les mises à jour Android. Refuse aussi un
# fichier .idsig posé à côté (signature v4, rejetée par la vérification de la release).
#
# Usage : verify-apk-cert.sh <apk>      (apksigner via BOBINE_ANDROID_BUILD_TOOLS ou le PATH)
set -euo pipefail

apk="${1:?chemin de l APK}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
pinned="$(tr -d '[:space:]' < "${root}/android/signing-certificate.sha256" | tr 'A-F' 'a-f')"
apksigner="${BOBINE_ANDROID_BUILD_TOOLS:+${BOBINE_ANDROID_BUILD_TOOLS}/}apksigner"

[[ "${pinned}" =~ ^[0-9a-f]{64}$ ]] || { echo "::error::android/signing-certificate.sha256 illisible"; exit 1; }
[[ ! -e "${apk}.idsig" ]] || { echo "::error::${apk}.idsig présent : signer avec --v4-signing-enabled false"; exit 1; }
output="$("${apksigner}" verify --print-certs "${apk}")"
found="$(printf "%s\n" "${output}" | grep -oiE "certificate SHA-256 digest: *[0-9a-f]{64}" | grep -oiE "[0-9a-f]{64}$" | tr A-F a-f | sort -u)"
[[ -n "${found}" ]] || { echo "::error::aucun certificat lisible dans ${apk}"; exit 1; }
if [[ "${found}" != "${pinned}" ]]; then
    echo "::error::certificat de ${apk} (${found}) différent de la clé de Bobine (${pinned})"
    exit 1
fi
echo "${apk} : signée par la clé de Bobine (${pinned})"

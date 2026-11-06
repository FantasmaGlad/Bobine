#!/usr/bin/env bash
# Vérifie les assets d'une release de l'assistant d'installation (tags assistant-Vx.y.z, assistant-beta,
# assistant-canary) avant publication : un paquet par système, listé dans SHA256SUMS avec sa vraie empreinte, rien d'autre.
# Les paquets de l'assistant ne vont jamais dans une release de Bobine : la mise à jour intégrée des installations
# existantes y prend le premier .exe, .deb ou .dmg de la bonne architecture.
#
# Usage : verify-assistant-assets.sh <dossier> <suffixe>   (5.1.1, beta ou canary)
set -euo pipefail

DIR="${1:?dossier des assets}"
S="${2:?suffixe de version (5.1.1, beta ou canary)}"

expected=(
    "bobine-assistant_${S}_amd64.deb"
    "bobine-assistant-${S}.x86_64.rpm"
    "Bobine-Assistant-Setup-${S}.exe"
    "Bobine-Assistant-${S}-arm64.dmg"
    "SHA256SUMS"
    "SHA256SUMS.asc"
)

for name in "${expected[@]}"; do
    [[ -s "${DIR}/${name}" ]] || { echo "::error::asset de l'assistant manquant ou vide : ${name}"; ls -l "${DIR}"; exit 1; }
done
extra=$(cd "${DIR}" && ls -1 | grep -vxF -f <(printf '%s\n' "${expected[@]}") || true)
[[ -z "${extra}" ]] || { echo "::error::fichiers inattendus dans la release de l'assistant : ${extra//$'\n'/ }"; exit 1; }
for name in "${expected[@]}"; do
    case "${name}" in SHA256SUMS|SHA256SUMS.asc) continue ;; esac
    grep -qE "^[0-9a-f]{64}  ${name//./\\.}$" "${DIR}/SHA256SUMS" || { echo "::error::${name} absent de SHA256SUMS"; exit 1; }
done
(cd "${DIR}" && sha256sum --check --strict SHA256SUMS > /dev/null) || { echo "::error::SHA256SUMS ne correspond pas aux fichiers"; exit 1; }
echo "Assets de l'assistant complets pour '${S}'."

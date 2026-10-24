#!/usr/bin/env bash
# Vérifie qu'un dossier d'assets de release contient TOUS les artefacts
# attendus avant publication, sous les noms exacts que consomment le site
# (bobine.fit, src/lib/github-releases.ts), les notes de release, le README et
# l'auto-mise à jour (backend/app/routers/updates.py).
#
# Sans ce contrôle, un job de build ignoré ou un artefact manquant donnait une
# release « verte » mais incomplète : les téléchargements du site retombaient
# silencieusement sur un lien mort.
#
# Usage : verify-release-assets.sh <dossier> <suffixe>
#   <suffixe> : numéro de version d'une Stable (5.0.0), ou l'identifiant d'un canal rolling (beta, canary).
set -euo pipefail

DIR="${1:?dossier des assets}"
S="${2:?suffixe de version (5.0.0, beta ou canary)}"

# Les canaux mobiles ont un nom constant ; les stables gardent le pkgrel natif.
# « Canal mobile » = canal rolling du registre (backend/app/release_channel.py).
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
    "bobine-assistant"
    "bobine-assistant-arm64"
    "install.sh"
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
echo "Tous les assets attendus (${#expected[@]}) sont présents pour '${S}'."

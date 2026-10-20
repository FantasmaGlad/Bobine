#!/usr/bin/env bash
# Vérifie qu'un APK déclare exactement les ABI natives attendues et que chacune
# embarque Python, et ffmpeg/ffprobe sur les ABI ARM.
#
# Garde-fou d'une régression déjà survenue : un APK Android TV sans dossier
# lib/armeabi-v7a s'installe sur les appareils 64 bits mais échoue avec
# INSTALL_FAILED_NO_MATCHING_ABIS sur tout boîtier TV dont le système est
# 32 bits (liste d'ABI = armeabi-v7a seule).
#
# Usage : verify-apk-abis.sh <apk> <abi> [<abi>...]
set -euo pipefail

APK="${1:?chemin de la cible APK}"
shift
(( $# > 0 )) || { echo "Au moins une ABI attendue" >&2; exit 2; }

AAPT2="$(ls "${ANDROID_HOME:?ANDROID_HOME requis}"/build-tools/*/aapt2 | sort -V | tail -1)"
declared="$("${AAPT2}" dump badging "${APK}" | sed -n "s/^native-code: //p" | tr -d "'" | tr ' ' '\n' | sort)"
expected="$(printf '%s\n' "$@" | sort)"

if [[ "${declared}" != "${expected}" ]]; then
    echo "::error::ABI de ${APK} : déclarées [$(echo "${declared}" | xargs)] ≠ attendues [$(echo "${expected}" | xargs)]"
    exit 1
fi

entries="$(unzip -Z1 "${APK}")"
for abi in "$@"; do
    # x86_64 (APK debug de l'émulateur de développement, jamais en release) : pas de ffmpeg embarqué.
    libs=(libpython3)
    [[ "${abi}" == x86_64 ]] || libs+=(libffmpeg.so libffprobe.so)
    for lib in "${libs[@]}"; do
        if ! grep -q "^lib/${abi}/${lib}" <<<"${entries}"; then
            echo "::error::${APK} : lib/${abi}/${lib}* absent"
            exit 1
        fi
    done
done
echo "${APK} : ABI [$(echo "${declared}" | xargs)] avec ses binaires embarqués."

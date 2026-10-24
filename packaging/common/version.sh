#!/usr/bin/env bash
# Décompose la VERSION de build (celle du champ Version: du .deb) en éléments RPM/pacman.
# À SOURCER. Entrée : $1 = version (ex. 5.0.5, 5.0.5+canary.42, 5.0.5+beta.7).
# Sortie (variables) : BASE_VERSION, CHANNEL (stable|beta|canary), RUN (numéro de build ou vide).
#
# Ordre voulu, identique au .deb (5.0.5 < 5.0.5+canary.7 < 5.0.6) :
#   RPM    : Version=BASE, Release=1 (stable) ou 1.<canal>.<run> (plus de segments = plus récent)
#   pacman : pkgver=BASE, pkgrel=1 (stable) ou 1.<run>  (un suffixe alphabétique trierait AVANT
#            la base dans libalpm, d'où le sous-numéro purement numérique)
BOBINE_VERSION_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# La règle (formes acceptées, canaux reconnus) n'est pas réécrite en shell : elle vient du registre
# unique backend/app/release_channel.py (parse_package_version), via channel.py. Prérequis : python3.
split_bobine_version() {
    local parsed
    parsed="$(python3 "${BOBINE_VERSION_SH_DIR}/channel.py" split-version "$1")" || return 1
    read -r BASE_VERSION CHANNEL RUN <<< "${parsed}"
}

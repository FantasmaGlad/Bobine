#!/usr/bin/env bash
# Décompose la VERSION de build (celle du champ Version: du .deb) en éléments RPM/pacman.
# À SOURCER. Entrée : $1 = version (ex. 5.0.5, 5.0.5+canary.42, 5.0.5+beta.7).
# Sortie (variables) : BASE_VERSION, CHANNEL (stable|beta|canary), RUN (numéro de build ou vide).
#
# Ordre voulu, identique au .deb (5.0.5 < 5.0.5+canary.7 < 5.0.6) :
#   RPM    : Version=BASE, Release=1 (stable) ou 1.<canal>.<run> (plus de segments = plus récent)
#   pacman : pkgver=BASE, pkgrel=1 (stable) ou 1.<run>  (un suffixe alphabétique trierait AVANT
#            la base dans libalpm, d'où le sous-numéro purement numérique)
split_bobine_version() {
    local v="$1"
    if [[ "$v" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\+(beta|canary)\.([0-9]+)$ ]]; then
        BASE_VERSION="${BASH_REMATCH[1]}"; CHANNEL="${BASH_REMATCH[2]}"; RUN="${BASH_REMATCH[3]}"
    elif [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        BASE_VERSION="$v"; CHANNEL="stable"; RUN=""
    else
        echo "Erreur: version '${v}' non reconnue (attendu x.y.z ou x.y.z+beta.N / x.y.z+canary.N)." >&2
        return 1
    fi
}

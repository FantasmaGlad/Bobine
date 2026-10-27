#!/usr/bin/env bash
# Décompose la VERSION de build (celle du champ Version: du .deb) en éléments RPM/pacman.
# À SOURCER. Entrée : $1 = version (5.0.6, 5.0.6~0.canary.42, 5.0.6~1.beta.7).
# Sortie : BASE_VERSION, CHANNEL, RUN, RPM_RELEASE, ARCH_VERSION.
# Canary < Bêta < Stable pour chaque version de base, selon les comparateurs natifs.
# Les anciennes formes +canal.N restent lisibles, sans être produites par la CI.
BOBINE_VERSION_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# La règle (formes acceptées, canaux reconnus) n'est pas réécrite en shell : elle vient du registre
# unique backend/app/release_channel.py (parse_package_version), via channel.py. Prérequis : python3.
split_bobine_version() {
    local parsed
    parsed="$(python3 "${BOBINE_VERSION_SH_DIR}/channel.py" package-fields "$1")" || return 1
    read -r BASE_VERSION CHANNEL RUN RPM_RELEASE ARCH_VERSION <<< "${parsed}"
}

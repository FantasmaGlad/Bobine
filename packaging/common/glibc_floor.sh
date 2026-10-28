#!/usr/bin/env bash
# Plancher de glibc des paquets Linux (.deb et .rpm). À SOURCER.
#
# Les binaires embarqués (exécutables Rust, amorce PyInstaller, bibliothèques) ne tournent que sur une glibc
# au moins aussi récente que leurs symboles les plus récents. Le plancher annoncé est écrit dans
# packaging/common/MIN_GLIBC : c'est lui que déclarent les paquets (libc6 pour le .deb, glibc pour le .rpm)
# et que cite la documentation. Chaque construction vérifie que les binaires n'exigent pas davantage : si
# l'image du runner change et relève l'exigence, la construction échoue au lieu de publier un paquet que des
# distributions annoncées ne pourraient plus lancer.

BOBINE_GLIBC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Plancher annoncé : fichier MIN_GLIBC (BOBINE_MIN_GLIBC_FILE le remplace pour les tests).
bobine_glibc_declared() {
    local file="${BOBINE_MIN_GLIBC_FILE:-${BOBINE_GLIBC_DIR}/MIN_GLIBC}"
    tr -d '[:space:]' < "${file}"
    echo
}

# Plus haut symbole GLIBC_x.y référencé par un exécutable ou une bibliothèque ELF de l'arbre $1
# (2.17 s'il n'y en a aucun).
bobine_glibc_required() {
    local tree="${1:?dossier à analyser}" required
    required="$(
        find "${tree}" -type f \( -perm -u+x -o -name '*.so*' \) -print0 \
        | xargs -0 -r grep -aoh -E 'GLIBC_[0-9]+\.[0-9]+(\.[0-9]+)?' 2>/dev/null \
        | sed 's/^GLIBC_//' | sort -uV | tail -n1 || true
    )"
    echo "${required:-2.17}"
}

# Affiche le plancher annoncé si les binaires de l'arbre $1 n'exigent pas davantage ; sinon explique et échoue.
bobine_glibc_check() {
    local tree="${1:?dossier à analyser}" declared required highest
    declared="$(bobine_glibc_declared)"
    required="$(bobine_glibc_required "${tree}")"
    highest="$(printf '%s\n%s\n' "${required}" "${declared}" | sort -V | tail -n1)"
    if [ "${highest}" != "${declared}" ]; then
        echo "Erreur: les binaires exigent glibc >= ${required}, plus que le plancher annoncé (${declared})." >&2
        echo "  Relevez packaging/common/MIN_GLIBC et la documentation des distributions prises en charge," >&2
        echo "  ou construisez sur une image dont la glibc est plus ancienne (runs-on dans ci.yml)." >&2
        return 1
    fi
    echo "${declared}"
}

# Ajoute libc6 (>= $2) en tête des dépendances du fichier DEBIAN/control $1.
bobine_deb_require_glibc() {
    local control="${1:?fichier DEBIAN/control}" floor="${2:?plancher glibc}"
    if ! grep -q '^Depends: ' "${control}"; then
        echo "Erreur: ${control} n'a pas de ligne Depends:" >&2
        return 1
    fi
    sed -i "s/^Depends: /Depends: libc6 (>= ${floor}), /" "${control}"
}

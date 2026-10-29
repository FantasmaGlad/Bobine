#!/usr/bin/env bash
# Ré-exporte et re-signe les fichiers Release (Release, InRelease, Release.gpg) de toutes les suites du dépôt APT, sans changer
# les paquets : la date et le Valid-Until repartent d'aujourd'hui. Dépendances : reprepro, GnuPG avec la clé de signature importée.
# Usage : refresh-apt-release.sh <copie du dépôt Pages>
set -euo pipefail
export LC_ALL=C
destination=$(realpath "${1:?copie du dépôt Pages}")
debian_dir="$destination/debian"
[ ! -L "$debian_dir" ] && [ -f "$debian_dir/conf/distributions" ] || { echo "Aucun dépôt APT dans $destination." >&2; exit 2; }
here=$(dirname "$0")
# Les suites existantes reçoivent la même durée que les nouvelles installations (la Beta passe de 30 jours à un an).
python3 "$here/apt-validity.py" apply "$debian_dir/conf/distributions"
reprepro -b "$debian_dir" export
python3 "$here/apt-validity.py" check "$debian_dir" "${BOBINE_MIN_VALID_DAYS:-14}"

#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
destination=$(realpath "${1:?copie du dépôt Pages}")
debian_dir="$destination/debian"
[ ! -L "$debian_dir" ] && [ -f "$debian_dir/conf/distributions" ] || { echo "Aucun dépôt APT dans $destination." >&2; exit 2; }
here=$(dirname "$0")
python3 "$here/apt-validity.py" apply "$debian_dir/conf/distributions"
reprepro -b "$debian_dir" export
python3 "$here/apt-validity.py" check "$debian_dir" "${BOBINE_MIN_VALID_DAYS:-14}"

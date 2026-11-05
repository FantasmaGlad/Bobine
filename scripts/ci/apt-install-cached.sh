#!/usr/bin/env bash
# Installe des paquets apt en gardant les .deb téléchargés dans un dossier que la CI met en cache : un miroir lent
# (plusieurs dizaines de secondes par paquet observées, jobs bloqués 20 min) ne coûte plus que le premier run d'une
# image. Arguments : dossier de cache, puis paquets ou fichiers .deb locaux à installer.
set -euo pipefail
cache="${1:?dossier de cache des paquets .deb}"
shift
mkdir -p "$cache/partial"
# shellcheck disable=SC2086 # APT_OPTIONS est une liste d'options
sudo apt-get ${APT_OPTIONS:-} update -qq
# shellcheck disable=SC2086
sudo apt-get ${APT_OPTIONS:-} install -y --no-install-recommends \
  -o Dir::Cache::Archives="$cache" -o APT::Keep-Downloaded-Packages=true "$@"
sudo chown -R "$(id -u):$(id -g)" "$cache"

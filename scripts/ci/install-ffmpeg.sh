#!/usr/bin/env bash
# Installe ffmpeg depuis Ubuntu en gardant les paquets .deb dans un dossier que la CI met en cache : un miroir lent
# (plusieurs dizaines de secondes par paquet observées) ne coûte plus que le premier run d'une image.
set -euo pipefail
cache="${1:?dossier de cache des paquets .deb}"
mkdir -p "$cache/partial"
# shellcheck disable=SC2086 # APT_OPTIONS est une liste d'options
sudo apt-get ${APT_OPTIONS:-} update -qq
# shellcheck disable=SC2086
sudo apt-get ${APT_OPTIONS:-} install -y --no-install-recommends \
  -o Dir::Cache::Archives="$cache" -o APT::Keep-Downloaded-Packages=true ffmpeg
sudo chown -R "$(id -u):$(id -g)" "$cache"
ffmpeg -hide_banner -version | head -n 1

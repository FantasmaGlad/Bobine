#!/usr/bin/env bash
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

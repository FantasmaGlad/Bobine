#!/usr/bin/env bash
set -euo pipefail
channel=$(sed -n 's/^channel = "\(.*\)"$/\1/p' "$(git rev-parse --show-toplevel)/rust-toolchain.toml")
if rustup toolchain list | grep -q "^$channel-"; then
  echo "Rust $channel déjà présent sur l'exécuteur, sans garantie sur ses composants : désinstallé avant une installation propre."
  rustup toolchain uninstall "$channel"
fi

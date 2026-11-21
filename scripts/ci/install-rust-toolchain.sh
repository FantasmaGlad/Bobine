#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
channel=$(sed -n 's/^channel = "\(.*\)"$/\1/p' "$root/rust-toolchain.toml")
if rustup toolchain list | grep -q "^$channel-"; then
  echo "Rust $channel déjà présent sur l'exécuteur, sans garantie sur ses composants : réinstallation propre."
  rustup toolchain uninstall "$channel"
fi
cd "$root"
rustup toolchain install

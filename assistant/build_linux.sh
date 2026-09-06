#!/usr/bin/env bash
# ==============================================================================
# Script de construction de l'Assistant d'installation Tauri pour Linux
# Génère le binaire natif de l'assistant
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=== [1/2] Compilation du binaire release Tauri pour Linux ==="
(cd "${SCRIPT_DIR}" && npx --yes @tauri-apps/cli build --no-bundle)

BIN_PATH="${SCRIPT_DIR}/target/release/bobine-assistant"
if [ ! -f "${BIN_PATH}" ]; then
    echo "Erreur: Le binaire release ${BIN_PATH} n'a pas été généré." >&2
    exit 1
fi

echo ""
echo "=== [2/2] Binaire natif Linux généré avec succès ==="
echo " Emplacement : ${BIN_PATH}"
echo " Taille      : $(du -h "${BIN_PATH}" | cut -f1)"
echo ""
echo "Pour lancer directement l'assistant :"
echo "  ${BIN_PATH}"

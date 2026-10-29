#!/usr/bin/env bash
#
# watchdog.sh — Chien de garde de santé de Bobine.
#
# Exécuté périodiquement par `bobine-watchdog.timer` (en root) : il consomme le
# point de contrôle `/api/health` du backend et redémarre tout composant mort.
# Complète `Restart=always` de systemd, qui ne couvre QUE la mort du *processus*
# — pas les défaillances *logiques* (backend vivant mais base verrouillée, ou
# Chromium gelé alors que l'unité kiosk reste "active").
#
#   1. Backend : si /api/health ne répond pas 200, on redémarre le backend.
#   2. Kiosque Chromium : si le service kiosk est activé mais qu'aucun processus
#      Chromium n'est présent (crash/gel de X), on redémarre bobine-kiosk.
#
# Idempotent et silencieux quand tout va bien ; chaque action est journalisée
# (journal systemd via `logger`, tag "bobine-watchdog").
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${BOBINE_CONFIG_FILE:-/etc/bobine/config.toml}"
RUNTIME_FILE="${BOBINE_RUNTIME_FILE:-${SCRIPT_DIR}/../backend/backend-runtime.json}"

log() { logger -t bobine-watchdog "$*" 2>/dev/null || true; }

# Port d'écoute du backend : celui que le processus vivant a publié dans son fichier d'exécution,
# sinon celui de la configuration (/etc/bobine/config.toml, écrit par install.sh), sinon 8000.
backend_port() {
    local port="" pid=""
    if [ -r "${RUNTIME_FILE}" ]; then
        port="$(sed -nE 's/.*"port"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' "${RUNTIME_FILE}" | head -n1)"
        pid="$(sed -nE 's/.*"pid"[[:space:]]*:[[:space:]]*([0-9]+).*/\1/p' "${RUNTIME_FILE}" | head -n1)"
        if [ -z "${pid}" ] || ! kill -0 "${pid}" 2>/dev/null; then
            port=""
        fi
    fi
    if [ -z "${port}" ] && [ -r "${CONFIG_FILE}" ]; then
        port="$(sed -nE 's/^[[:space:]]*port[[:space:]]*=[[:space:]]*([0-9]+).*/\1/p' "${CONFIG_FILE}" | head -n1)"
    fi
    echo "${port:-8000}"
}
HEALTH_URL="http://127.0.0.1:$(backend_port)/api/health"

# 1) Backend ------------------------------------------------------------------
code="$(curl -s -o /dev/null -m 5 -w '%{http_code}' "${HEALTH_URL}" 2>/dev/null || echo 000)"
if [ "${code}" != "200" ]; then
    log "sante backend degradee (http=${code}) : redemarrage du backend"
    systemctl restart bobine-backend.service
fi

# 2) Kiosque Chromium --------------------------------------------------------
# Seulement si le service kiosk est censé tourner (pas en mode --no-kiosk).
if systemctl is-enabled --quiet bobine-kiosk.service 2>/dev/null; then
    if ! pgrep -x chromium >/dev/null 2>&1 && ! pgrep -x chromium-browser >/dev/null 2>&1; then
        log "aucun processus Chromium kiosque detecte : redemarrage de bobine-kiosk"
        systemctl restart bobine-kiosk.service
    fi
fi

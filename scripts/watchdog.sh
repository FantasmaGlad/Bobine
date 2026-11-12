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
#   0. Mise à jour récente : si la santé n'est pas bonne à l'échéance, retour à la version précédente.
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
# sinon celui de la configuration (/etc/bobine/config.toml, écrit par install.sh), sinon 1903.
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
    echo "${port:-1903}"
}
HEALTH_URL="http://127.0.0.1:$(backend_port)/api/health"

# 0) Mise à jour en attente de confirmation -------------------------------------
# Le backend écrit ce fichier juste avant de se redémarrer sur une nouvelle version (profil appliance). Tant
# que la santé n'est pas bonne, on lui laisse jusqu'à l'échéance ; passé ce délai, la version précédente est
# restaurée. Ce contrôle vit ici parce qu'un backend qui ne démarre plus ne peut pas se réparer lui-même.
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PENDING_FILE="${BOBINE_PENDING_UPDATE_FILE:-${REPO_DIR}/backend/update-pending.json}"
STALE_PENDING_SECONDS=3600

json_field() { sed -nE "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"?([^\",}]+)\"?.*/\1/p" "${PENDING_FILE}" | head -n1; }

update_is_healthy() {
    local body
    body="$(curl -s -m 5 "${HEALTH_URL}" 2>/dev/null)" || return 1
    # Une version plus ancienne (retour arrière voulu) n'annonce ni planificateur ni interface : seule leur
    # panne déclarée compte comme un échec.
    case "${body}" in
        *'"scheduler":"down"'*|*'"frontend":"missing"'*) return 1 ;;
        *'"status":"ok"'*) return 0 ;;
        *) return 1 ;;
    esac
}

as_owner() { runuser -u "$(stat -c %U "${REPO_DIR}")" -- "$@"; }

roll_back_update() {
    local previous="$1"
    log "mise a jour non confirmee : retour a ${previous}"
    as_owner git -C "${REPO_DIR}" checkout --quiet "${previous}" || { log "retour arriere impossible : git checkout ${previous} a echoue"; return 1; }
    if [ -x "${REPO_DIR}/backend/.venv/bin/pip" ]; then
        as_owner "${REPO_DIR}/backend/.venv/bin/pip" install -q -r "${REPO_DIR}/backend/requirements.txt" || log "retour arriere : pip install a echoue"
    fi
    # Le service revient tout de suite sur l'ancien code ; l'interface est reconstruite ensuite (plusieurs minutes).
    systemctl restart bobine-backend.service
    if (cd "${REPO_DIR}/frontend" && as_owner npm ci --no-audit --no-fund && as_owner npm run build) >/dev/null 2>&1; then
        systemctl restart bobine-backend.service
        systemctl is-enabled --quiet bobine-kiosk.service 2>/dev/null && systemctl restart bobine-kiosk.service
        log "version precedente restauree (${previous})"
    else
        log "retour arriere : reconstruction de l'interface en echec"
    fi
}

if [ -r "${PENDING_FILE}" ]; then
    previous_ref="$(json_field previous_ref)"
    deadline="$(json_field deadline)"
    # Marqueur d'une mise à jour ancienne (machine éteinte entre-temps, version sans ce contrôle) : sans objet.
    if [ "$(date +%s)" -ge "$(( ${deadline:-0} + STALE_PENDING_SECONDS ))" ]; then
        rm -f "${PENDING_FILE}"
    elif update_is_healthy; then
        log "mise a jour confirmee par le controle de sante"
        rm -f "${PENDING_FILE}"
    elif [ -n "${previous_ref}" ] && [ "$(date +%s)" -ge "${deadline:-0}" ]; then
        rm -f "${PENDING_FILE}"
        roll_back_update "${previous_ref}"
        exit 0
    else
        exit 0  # le nouveau backend démarre encore : ni redémarrage ni retour arrière avant l'échéance
    fi
fi

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

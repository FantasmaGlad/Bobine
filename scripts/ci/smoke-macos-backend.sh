#!/usr/bin/env bash
# Sonde de santé du backend macOS : lance l'exécutable, attend HTTP 200 sur /api/health, l'arrête
# et libère le port. Partagée par la sonde du bundle PyInstaller et celle du Bobine.app copié
# depuis le dmg monté.
#
# Usage : smoke-macos-backend.sh <BobineBackend> [--home DIR] [--log-dir DIR] [--attempts N]
# --home isole les données : le backend les range sous ~/Library/Application Support/Bobine,
# HOME est donc redéfini pour le seul processus lancé. Le port 8000 est imposé par
# backend/run_backend.py : la sonde refuse de démarrer s'il est déjà occupé.
set -euo pipefail

exe="${1:?chemin de BobineBackend requis}"
shift
home_dir=""
log_dir=""
attempts=20
port=8000
while (( $# > 0 )); do
  case "$1" in
    --home) home_dir="${2:?}"; shift 2 ;;
    --log-dir) log_dir="${2:?}"; shift 2 ;;
    --attempts) attempts="${2:?}"; shift 2 ;;
    *) echo "Option inconnue : $1" >&2; exit 2 ;;
  esac
done

exe="$(cd "$(dirname "$exe")" && pwd -P)/$(basename "$exe")"
[[ -x "$exe" ]] || { echo "Exécutable introuvable : $exe" >&2; exit 2; }
log_dir="${log_dir:-$(dirname "$exe")}"
mkdir -p "$log_dir"
log_dir="$(cd "$log_dir" && pwd -P)"
if [[ -n "$home_dir" ]]; then
  mkdir -p "$home_dir"
  home_dir="$(cd "$home_dir" && pwd -P)"
fi
err_log="$log_dir/backend_err.log"
out_log="$log_dir/backend_out.log"
rm -f "$err_log" "$out_log"

listeners() { lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true; }
if [[ -n "$(listeners)" ]]; then
  echo "Le port $port est déjà occupé avant le lancement de $exe" >&2
  exit 1
fi

pid=""
stop_backend() {
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
  for _ in $(seq 1 10); do [[ -z "$(listeners)" ]] && break; sleep 1; done
}
trap stop_backend EXIT

cd "$(dirname "$exe")"
if [[ -n "$home_dir" ]]; then
  HOME="$home_dir" "$exe" >"$out_log" 2>"$err_log" &
else
  "$exe" >"$out_log" 2>"$err_log" &
fi
pid=$!

ready=0
reason="aucune réponse HTTP 200 après $attempts essais"
for _ in $(seq 1 "$attempts"); do
  sleep 1
  if ! kill -0 "$pid" 2>/dev/null; then
    wait "$pid" && code=0 || code=$?
    reason="le processus s'est arrêté (code $code) avant de répondre"
    pid=""
    break
  fi
  if body="$(curl -sf --max-time 2 "http://127.0.0.1:$port/api/health" 2>/dev/null)"; then
    listener="$(listeners | head -n1)"
    if [[ "$listener" != "$pid" ]]; then
      reason="la réponse ne vient pas du processus lancé (écouteur $listener, lancé $pid)"
      break
    fi
    ready=1
    echo "Backend opérationnel ($exe) : $body"
    break
  fi
done

if [[ -n "$home_dir" ]]; then
  echo "=== Données isolées sous $home_dir ==="
  find "$home_dir" -maxdepth 4 | head -n 40
fi
if (( ! ready )); then
  echo "=== Échec : $reason ==="
  echo "=== Backend stderr ==="; cat "$err_log" 2>/dev/null || true
  echo "=== Backend stdout ==="; cat "$out_log" 2>/dev/null || true
  exit 1
fi

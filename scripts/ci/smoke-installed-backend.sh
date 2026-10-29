#!/usr/bin/env bash
# Lance le backend INSTALLÉ par un paquet Linux et exige HTTP 200 sur /api/health, comme les jobs Windows et macOS.
# À lancer après l'installation du paquet (runner ou conteneur), jamais sur l'arbre de construction.
# Isolation : HOME, XDG_DATA_HOME, XDG_CONFIG_HOME et XDG_CACHE_HOME dans un dossier temporaire, BOBINE_USE_XDG=1.
# Le port est celui de run_backend.py (8000, fixé dans l'exécutable) : le script refuse de démarrer s'il est déjà occupé.
# Usage : smoke-installed-backend.sh [exécutable]   (défaut : /usr/lib/bobine/BobineBackend)
set -euo pipefail
backend="${1:-/usr/lib/bobine/BobineBackend}"
port=8000
attempts="${BOBINE_SMOKE_ATTEMPTS:-30}"

[ -x "$backend" ] || { echo "Erreur: $backend n'est pas exécutable." >&2; exit 1; }
command -v curl >/dev/null || { echo "Erreur: curl est requis." >&2; exit 1; }
if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "Erreur: le port $port est déjà occupé, le résultat serait trompeur." >&2
    exit 1
fi

work="$(mktemp -d)"
pid=""
stop() {
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 10); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -rf "$work"
}
trap stop EXIT
mkdir -p "$work/home" "$work/data" "$work/config" "$work/cache"

echo "=== $backend : démarrage isolé, port $port ==="
HOME="$work/home" XDG_DATA_HOME="$work/data" XDG_CONFIG_HOME="$work/config" XDG_CACHE_HOME="$work/cache" BOBINE_USE_XDG=1 \
    "$backend" > "$work/backend.log" 2>&1 &
pid=$!

for _ in $(seq 1 "$attempts"); do
    if ! kill -0 "$pid" 2>/dev/null; then
        wait "$pid" && code=0 || code=$?
        echo "Erreur: le backend s'est arrêté avant de répondre (code $code)." >&2
        pid=""
        tail -n 100 "$work/backend.log" >&2
        exit 1
    fi
    status="$(curl -s -o "$work/health.json" -w '%{http_code}' --max-time 2 "http://127.0.0.1:$port/api/health" || true)"
    if [ "$status" = 200 ]; then
        echo "Backend installé opérationnel : $(cat "$work/health.json")"
        exit 0
    fi
    sleep 1
done
echo "Erreur: pas de HTTP 200 sur /api/health après $attempts essais (dernier code : ${status:-aucun})." >&2
tail -n 100 "$work/backend.log" >&2
exit 1

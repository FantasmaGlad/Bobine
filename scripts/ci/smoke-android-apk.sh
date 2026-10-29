#!/usr/bin/env bash
# Démarre le vrai service Chaquopy et attend une base SQLite opérationnelle.
# Usage : smoke-android-apk.sh mobile|tv [chemin.apk] ; émulateur jetable uniquement.
# Le port d'écoute n'est pas imposé : le serveur embarqué choisit son port et le publie dans
# files/backend-runtime.json (app/utils/port.py). La sonde le lit par `run-as` (APK de debug),
# redirige CE port et sonde l'API par là. Le repli sur un port libre n'est pas exercé ici : seul
# le port publié par le serveur est sondé.
set -euo pipefail
flavor="${1:?flavor mobile ou tv requis}"
case "$flavor" in
  mobile) package=com.bobine.app ;;
  tv) package=com.bobine.app.tv ;;
  *) echo "Flavor inconnu : $flavor" >&2; exit 2 ;;
esac
apk="${2:-android/app/build/outputs/apk/$flavor/debug/app-$flavor-debug.apk}"
logs=android-startup-logs
mkdir -p "$logs"
cleanup() {
  adb logcat -d -v threadtime > "$logs/logcat-$flavor.txt" || true
  adb shell dumpsys activity services "$package" > "$logs/services-$flavor.txt" || true
  adb exec-out screencap -p > "$logs/screen-$flavor.png" || true
  if [[ -n "${port:-}" ]]; then adb forward --remove "tcp:$port" || true; fi
}
# Refuser un appareil réel : ce script installe un APK de test sur un AVD dédié.
[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == 1 ]] || {
  echo "Un émulateur Android jetable est requis." >&2; exit 2;
}
trap cleanup EXIT
# Les deux variantes exposent le même port dans l'appareil de test.
adb shell am force-stop com.bobine.app
adb shell am force-stop com.bobine.app.tv
adb install --no-streaming -r -g "$apk"
adb shell pm clear "$package"
adb logcat -c
adb shell am start -W -n "$package/com.bobine.app.MainActivity"
device_port=""
for _ in $(seq 1 120); do
  if [[ -z "$device_port" ]]; then
    device_port=$(adb shell "run-as $package cat files/backend-runtime.json" 2>/dev/null | tr -d '\r' | python3 -c 'import json,sys
try:
    print(int(json.load(sys.stdin)["port"]))
except Exception:
    pass' || true)
    if [[ -n "$device_port" ]]; then
      port=$(adb forward tcp:0 "tcp:$device_port")
      echo "Le serveur embarqué écoute sur le port $device_port de l'appareil."
    fi
  fi
  if [[ -n "${port:-}" ]] && curl --max-time 2 -fsS "http://127.0.0.1:$port/api/health" > "$logs/health-$flavor.json" 2>/dev/null; then
    python3 -c 'import json,sys; p=json.load(open(sys.argv[1])); assert p["status"] == "ok" and p["components"]["database"] == "ok", p' "$logs/health-$flavor.json"
    # L'API et le frontend embarqué doivent tous deux être servis par l'APK.
    curl --max-time 10 -fsS "http://127.0.0.1:$port/api/settings" > "$logs/settings-$flavor.json"
    curl --max-time 10 -fsS "http://127.0.0.1:$port/" > "$logs/index-$flavor.html"
    grep -qi '<html' "$logs/index-$flavor.html"
    echo "APK $flavor : backend, SQLite, réglages et frontend disponibles."
    exit 0
  fi
  sleep 2
done
if [[ -z "$device_port" ]]; then
  echo "Le serveur embarqué n'a publié aucun port (files/backend-runtime.json absent ou illisible)." >&2
fi
echo "Le serveur embarqué n'est pas devenu opérationnel dans le délai prévu." >&2
exit 1

#!/usr/bin/env bash
# Démarre le vrai service Chaquopy et attend une base SQLite opérationnelle.
# Usage : smoke-android-apk.sh mobile|tv [chemin.apk] ; émulateur jetable uniquement.
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
port=$(adb forward tcp:0 tcp:8000)
adb shell am start -W -n "$package/com.bobine.app.MainActivity"
for _ in $(seq 1 120); do
  if curl --max-time 2 -fsS "http://127.0.0.1:$port/api/health" > "$logs/health-$flavor.json" 2>/dev/null; then
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
echo "Le serveur embarqué n'est pas devenu opérationnel dans le délai prévu." >&2
exit 1

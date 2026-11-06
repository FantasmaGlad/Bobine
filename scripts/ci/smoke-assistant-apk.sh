#!/usr/bin/env bash
# Installe l'APK de l'assistant d'installation sur un émulateur jetable, la lance et vérifie qu'elle tient 15 s
# sans plantage ni panique Rust (interface WebView et bibliothèque native chargées).
# Usage : smoke-assistant-apk.sh <apk> ; une APK non signée (PR sans secrets) est signée d'une clé jetable.
set -euo pipefail
apk="${1:?chemin de l’APK requis}"
package=com.bobine.assistant
logs=assistant-android-logs
mkdir -p "$logs"
[[ "$(adb shell getprop ro.kernel.qemu | tr -d '\r')" == 1 ]] || { echo "Un émulateur Android jetable est requis." >&2; exit 2; }
cleanup() {
  adb logcat -d -v threadtime > "$logs/logcat.txt" || true
  adb exec-out screencap -p > "$logs/screen.png" || true
}
trap cleanup EXIT

tools="${BOBINE_ANDROID_BUILD_TOOLS:?BOBINE_ANDROID_BUILD_TOOLS non défini}"
if ! "$tools/apksigner" verify "$apk" > /dev/null 2>&1; then
  keystore="$RUNNER_TEMP/assistant-essai.keystore"
  keytool -genkeypair -keystore "$keystore" -storepass essai-jetable -keypass essai-jetable -alias essai \
    -keyalg RSA -keysize 2048 -validity 1 -dname "CN=Essai CI" > /dev/null 2>&1
  "$tools/apksigner" sign --ks "$keystore" --ks-pass pass:essai-jetable --out "$RUNNER_TEMP/assistant-essai.apk" "$apk"
  apk="$RUNNER_TEMP/assistant-essai.apk"
fi

adb install --no-streaming -r "$apk"
adb logcat -c
adb shell am start -W -n "$package/.MainActivity"
sleep 15
pid=$(adb shell pidof "$package" | tr -d '\r')
[[ -n "$pid" ]] || { echo "::error::l'assistant s'est arrêté au démarrage" >&2; exit 1; }
if adb logcat -d | grep -E "FATAL EXCEPTION|panicked at|Fatal signal" | grep -v "^--------- " > "$logs/erreurs.txt"; then
  cat "$logs/erreurs.txt" >&2
  echo "::error::plantage de l'assistant détecté dans logcat" >&2
  exit 1
fi
echo "Assistant Android lancé (pid $pid)."

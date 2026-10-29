#!/usr/bin/env bash
# Cycle de vie réel du .dmg dans la CI macOS : montage en lecture seule, contenu, copie de
# Bobine.app dans un dossier temporaire, signature du bundle copié, lancement de son backend
# (smoke-macos-backend.sh), puis démontage. La signature est ad hoc : Gatekeeper n'est pas exercé.
#
# Usage : smoke-macos-dmg.sh <Bobine.dmg> <dossier de travail>
set -euo pipefail

dmg="${1:?chemin du .dmg requis}"
work="${2:?dossier de travail requis}"
here="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$dmg" ]] || { echo "dmg introuvable : $dmg" >&2; exit 2; }

mkdir -p "$work"
mount_point="$(mktemp -d "$work/mnt.XXXXXX")"
copy_dir="$(mktemp -d "$work/copie.XXXXXX")"
mounted=0
cleanup() {
  if (( mounted )); then
    hdiutil detach "$mount_point" || hdiutil detach -force "$mount_point" || true
  fi
}
trap cleanup EXIT

ls -l "$dmg"
hdiutil verify "$dmg"
hdiutil attach "$dmg" -readonly -nobrowse -noautoopen -mountpoint "$mount_point"
mounted=1

echo "=== Contenu du volume monté ==="
ls -la "$mount_point"
[[ -d "$mount_point/Bobine.app" ]] || { echo "Bobine.app absent du dmg" >&2; exit 1; }
[[ -L "$mount_point/Applications" && "$(readlink "$mount_point/Applications")" == /Applications ]] || {
  echo "Lien Applications absent ou incorrect dans le dmg" >&2; exit 1;
}

# ditto conserve signature, attributs étendus et liens symboliques du bundle.
ditto "$mount_point/Bobine.app" "$copy_dir/Bobine.app"
backend="$copy_dir/Bobine.app/Contents/MacOS/BobineBackend"
for required in BobineBackend bobine-projector bobine-devices bobine-media; do
  [[ -x "$copy_dir/Bobine.app/Contents/MacOS/$required" ]] || { echo "Contents/MacOS/$required absent ou non exécutable" >&2; exit 1; }
done
[[ -f "$copy_dir/Bobine.app/Contents/Resources/bobine.icns" ]] || { echo "bobine.icns absent du bundle copié" >&2; exit 1; }
codesign --verify --deep --strict --verbose=1 "$copy_dir/Bobine.app"

"$here/smoke-macos-backend.sh" "$backend" --home "$work/home" --log-dir "$work/logs"

cleanup
mounted=0
if mount | grep -F -q "$mount_point"; then
  echo "Le volume est encore monté après hdiutil detach : $mount_point" >&2
  exit 1
fi
echo "dmg monté, copié, lancé et démonté."

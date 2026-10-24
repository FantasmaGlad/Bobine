#!/usr/bin/env bash
# Contrôles du paquet Arch, à lancer DANS un conteneur archlinux (root) :
#   pacman -Qip/-Qlp, namcap, installation réelle (pacman -U), fichiers, désinstallation.
# Usage : test_arch.sh <fichier.pkg.tar.zst> [--no-install]   (--no-install : paquet d'une autre architecture)
set -euo pipefail
PKG_FILE="${1:?fichier .pkg.tar.zst}"
INSTALL=1; [ "${2:-}" = "--no-install" ] && INSTALL=0
pacman -Syu --noconfirm --needed namcap python >/dev/null

echo "=== pacman -Qip / -Qlp ==="
pacman -Qip "${PKG_FILE}"
pacman -Qlp "${PKG_FILE}"

echo "=== namcap ==="
# Filtres : exécutables du bundle sans bibliothèques liées dynamiquement à la mode Arch
# (PyInstaller embarque les siennes), bibliothèques « non-nécessaires », fichiers .so privés.
namcap "${PKG_FILE}" | tee /tmp/namcap.out
python3 - "$PKG_FILE" /tmp/namcap.out <<'PYFILTER'
import ast, pathlib, re, subprocess, sys
files=set(subprocess.check_output(['tar','--zstd','-tf',sys.argv[1]],text=True).splitlines())
errors=[]
for line in pathlib.Path(sys.argv[2]).read_text().splitlines():
    if ' E: ' not in line: continue
    # Namcap cherche les bibliothèques dans /usr/lib ; PyInstaller les embarque dans son répertoire privé.
    match=re.search(r"Dependency \w+ detected and not included \(libraries (\[.*?\])",line)
    if match and all('usr/lib/bobine/'+pathlib.PurePosixPath(lib).name in files for lib in ast.literal_eval(match[1])):
        continue
    if re.search(r'unknown-dep|script-link-detected|elf-unusual-bin-path|unstripped|incorrect-library|no-dep|usr-lib',line): continue
    errors.append(line)
if errors: raise SystemExit('\n'.join(errors))
PYFILTER

[ "${INSTALL}" = "1" ] || exit 0
echo "=== installation réelle ==="
pacman -U --noconfirm "${PKG_FILE}"
test -x /usr/bin/bobine
test -x /usr/lib/bobine/BobineBackend
test -x /usr/lib/bobine/BobineTray
test -f /usr/share/applications/com.bobine.app.desktop
test -f /etc/xdg/autostart/com.bobine.app.desktop
test -f /usr/share/metainfo/com.bobine.app.metainfo.xml
test -f /usr/lib/systemd/user/bobine.service
test -f /usr/share/icons/hicolor/256x256/apps/bobine.png
test -f /usr/share/pixmaps/bobine.png
if [ -e /usr/lib/bobine/bobine-media ]; then test -x /usr/lib/bobine/bobine-media; fi
# L'image conteneur exclut /usr/share/doc (NoExtract) : seul ce répertoire peut manquer.
if ! pacman -Qkk bobine 2>&1 | tee /tmp/qkk.out | tail -n 3; then
    grep -E 'warning: bobine: ' /tmp/qkk.out | grep -v '/usr/share/doc' && { echo "fichiers manquants/altérés"; exit 1; }
fi
echo "=== réinstallation ==="
pacman -U --noconfirm "${PKG_FILE}"
echo "=== désinstallation ==="
pacman -R --noconfirm bobine
test ! -e /usr/lib/bobine
echo "ARCH OK"

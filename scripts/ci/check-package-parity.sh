#!/usr/bin/env bash
# Vérifie que les paquets .deb, .rpm et Arch (.pkg.tar.zst) d'une même construction contiennent
# les MÊMES fichiers (chemins) — l'arbre PyInstaller étant partagé, toute divergence signale
# une erreur de packaging. Écarts volontaires, listés ici et nulle part ailleurs :
#   - .deb seul : /usr/share/appdata/… (ancien chemin AppStream, doublon du metainfo) ;
#   - .rpm seul : /usr/lib/firewalld/services/bobine.xml (définition de service, n'ouvre rien) ;
#   - Arch seul : /usr/share/licenses/bobine/… (convention Arch pour la licence) ;
#   - répertoires non comparés ; /usr/share/doc/bobine/copyright : fichier de licence présent partout
#     (Arch en plus sous /usr/share/licenses).
# Usage : check-package-parity.sh <.deb> <.rpm> <.pkg.tar.zst>
# Outils : dpkg-deb, rpm (ou rpm2cpio+cpio), tar avec zstd.
set -euo pipefail
DEB="${1:?fichier .deb}"; RPM="${2:?fichier .rpm}"; PKG="${3:?fichier .pkg.tar.zst}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# Lire les membres de l'archive, pas la sortie destinée à l'humain de dpkg -c :
# celle-ci contient des espaces et « lien -> cible », que awk tronquerait.
python3 - "$DEB" "$T/deb" <<'PYDEB'
import subprocess, sys, tarfile
process = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', sys.argv[1]], stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
    paths = sorted('/' + item.name.removeprefix('./').lstrip('/') for item in archive if not item.isdir())
if process.wait():
    raise SystemExit('Archive Debian illisible')
with open(sys.argv[2], 'w') as output:
    output.write('\n'.join(paths) + '\n')
PYDEB
if command -v rpm >/dev/null 2>&1; then
    rpm -qlp "$RPM" | sort > "$T/rpm.all"
else
    rpm2cpio "$RPM" | cpio -t --quiet 2>/dev/null | sed 's|^\./|/|' | sort > "$T/rpm.all"
fi
# rpm -ql liste aussi les répertoires : ne garder que ce qui a un équivalent fichier (on retire ceux
# qui sont des préfixes d'un autre chemin de la liste).
python3 - "$T/rpm.all" "$T/rpm" <<'PY'
import sys
paths = [l.rstrip("\n") for l in open(sys.argv[1]) if l.strip()]
dirs = {p for q in paths for p in [q.rsplit("/", 1)[0]] if p}
parents = set()
for q in paths:
    parent = q
    while "/" in parent.strip("/"):
        parent = parent.rsplit("/", 1)[0]
        parents.add(parent)
open(sys.argv[2], "w").write("\n".join(sorted(p for p in paths if p not in parents)) + "\n")
PY
tar --zstd -tf "$PKG" | grep -v '/$' | grep -v '^\.' | sed 's|^|/|' | sort > "$T/pkg"

filter() { grep -v -e '^/usr/share/appdata/' -e '^/usr/lib/firewalld/' -e '^/usr/share/licenses/' "$1" | sed '/^$/d' | sort -u; }
# Les fichiers de l'arbre PyInstaller sont comparés tels quels ; les liens symboliques peuvent
# apparaître différemment selon l'outil : on compare les chemins.
filter "$T/deb" > "$T/deb.f"; filter "$T/rpm" > "$T/rpm.f"; filter "$T/pkg" > "$T/pkg.f"
rc=0
for other in rpm pkg; do
    if ! diff -u "$T/deb.f" "$T/$other.f" > "$T/diff.$other"; then
        echo "::error::Écart de contenu entre .deb et ${other} :"; cat "$T/diff.$other"; rc=1
    fi
done
[ "$rc" = 0 ] && echo "Parité OK : $(wc -l < "$T/deb.f") fichiers identiques dans .deb, .rpm et Arch."
exit "$rc"

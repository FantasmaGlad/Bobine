#!/usr/bin/env bash
set -euo pipefail
DEB="${1:?fichier .deb}"; RPM="${2:?fichier .rpm}"; PKG="${3:?fichier .pkg.tar.zst}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

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
filter "$T/deb" > "$T/deb.f"; filter "$T/rpm" > "$T/rpm.f"; filter "$T/pkg" > "$T/pkg.f"
rc=0
for other in rpm pkg; do
    if ! diff -u "$T/deb.f" "$T/$other.f" > "$T/diff.$other"; then
        echo "::error::Écart de contenu entre .deb et ${other} :"; cat "$T/diff.$other"; rc=1
    fi
done
[ "$rc" = 0 ] && echo "Parité OK : $(wc -l < "$T/deb.f") fichiers identiques dans .deb, .rpm et Arch."
exit "$rc"

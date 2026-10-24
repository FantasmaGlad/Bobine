#!/usr/bin/env python3
"""Retire les chemins de construction des ELF Linux en conservant leurs chemins relatifs ($ORIGIN)."""
import pathlib
import shutil
import subprocess
import sys

root = pathlib.Path(sys.argv[1]).resolve(strict=True)
if not shutil.which('patchelf'):
    raise SystemExit('patchelf est requis pour assainir le bundle Linux.')
changed = 0
for path in root.rglob('*'):
    if path.is_symlink() or not path.is_file():
        continue
    with path.open('rb') as stream:
        if stream.read(4) != b'\x7fELF':
            continue
    result = subprocess.run(['patchelf', '--print-rpath', str(path)], capture_output=True, text=True)
    if result.returncode:
        raise SystemExit(f'ELF illisible : {path.name}')
    entries = result.stdout.strip().split(':')
    clean = [item for item in entries if item and not item.startswith(('/opt/hostedtoolcache/', '/home/runner/work/'))]
    if clean != [item for item in entries if item]:
        command = ['patchelf', '--set-rpath', ':'.join(clean), str(path)] if clean else ['patchelf', '--remove-rpath', str(path)]
        subprocess.run(command, check=True)
        changed += 1
print(f'Bundle Linux : {changed} chemin(s) de construction retiré(s).')

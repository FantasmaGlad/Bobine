#!/usr/bin/env python3
"""Vérifie le refus des dépôts incomplets ou altérés à partir d'une copie signée."""
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('packages', Path(__file__).with_name('verify-package-repository.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
source = Path(sys.argv[1]).resolve()
module.verify(source)

cases = {
    'clé absente': 'bobine.gpg',
    'signature APT': 'debian/dists/stable/InRelease',
    'index APT': 'debian/dists/stable/main/binary-amd64/Packages',
    'signature DNF': 'fedora/stable/x86_64/repodata/repomd.xml.asc',
    'signature Pacman': 'arch/stable/x86_64/bobine.db.sig',
}
for label, pattern in [('binaire APT', 'debian/pool/**/*.deb'),
                       ('binaire RPM', 'fedora/stable/x86_64/*.rpm'),
                       ('binaire Arch', 'arch/stable/x86_64/*.pkg.tar.zst')]:
    cases[label] = str(next(source.glob(pattern)).relative_to(source))

for label, relative in cases.items():
    with tempfile.TemporaryDirectory(dir=source.parent) as temporary:
        root = Path(temporary) / 'repository'
        shutil.copytree(source, root, copy_function=os.link)
        target = root / relative
        data = target.read_bytes()
        target.unlink()
        if label != 'clé absente':
            target.write_bytes(data[:len(data) // 2] + b'corruption' + data[len(data) // 2:])
        try:
            module.verify(root)
        except (ValueError, KeyError, IndexError, OSError, module.subprocess.CalledProcessError):
            print(f'Refus conforme : {label}')
        else:
            sys.exit(f'Dépôt altéré accepté : {label}')
print(f'{len(cases)} altérations refusées')

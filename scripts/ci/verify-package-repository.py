#!/usr/bin/env python3
"""Vérifie la chaîne signée des trois dépôts avant toute publication locale."""
import email.utils
import gzip
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

PRIMARY = 'B77D96D72F84F36ACAA3F8729CBF497D829EE15A'
CHANNELS = ('stable', 'beta', 'canary')


def fields(text):
    return dict(re.findall(r'^([A-Za-z0-9-]+): (.*)$', text, re.M))


def verify(root):
    root = root.resolve()

    def path(base, name):
        target = (base / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise ValueError(f'fichier absent ou chemin interdit : {target}')
        return target

    def checksum(file, expected, size=None):
        if size is not None and file.stat().st_size != int(size):
            raise ValueError(f'taille incorrecte : {file}')
        with file.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected.lower():
            raise ValueError(f'SHA-256 incorrect : {file}')

    versions = {}
    bobine = {}
    with tempfile.TemporaryDirectory() as home:
        def gpg(*args, output=False):
            result = subprocess.run(['gpg', '--homedir', home, '--batch', *args],
                                    check=True, capture_output=True, text=True)
            return result.stdout if output else None

        key = path(root, 'bobine.gpg')
        listed = gpg('--with-colons', '--show-keys', str(key), output=True)
        fingerprints = re.findall(r'^fpr:::::::::([A-F0-9]+):', listed, re.M)
        if not fingerprints or fingerprints[0] != PRIMARY or len(re.findall(r'^pub:', listed, re.M)) != 1:
            raise ValueError('empreinte principale inattendue ou plusieurs clés')
        gpg('--import', str(key))

        def signature(file, suffix):
            gpg('--verify', str(path(file.parent, file.name + suffix)), str(file))

        for channel in CHANNELS:
            suite = root / 'debian/dists' / channel
            release = gpg('--decrypt', str(path(suite, 'InRelease')), output=True)
            expires = fields(release).get('Valid-Until')
            if expires and email.utils.parsedate_to_datetime(expires).timestamp() < time.time():
                raise ValueError(f'Release expiré : {channel}')
            section = release.split('\nSHA256:\n', 1)[1].split('\n\n', 1)[0]
            authenticated = set()
            count = 0
            for digest, size, name in re.findall(r'^ ([a-f0-9]{64})\s+(\d+)\s+(\S+)$', section, re.M):
                checksum(path(suite, name), digest, size)
                authenticated.add(name)
                count += 1
            if not count:
                raise ValueError(f'aucune somme SHA-256 : {channel}')
            for arch in ('amd64', 'arm64'):
                index = f'main/binary-{arch}/Packages'
                if index not in authenticated:
                    raise ValueError(f'index APT non authentifié : {index}')
                packages = path(suite, index)
                records = [fields(block) for block in packages.read_text().strip().split('\n\n')]
                if not records:
                    raise ValueError(f'index APT vide : {packages}')
                versions[f'apt/{channel}/{arch}'] = [record['Version'] for record in records]
                bobine[f'{channel}/{arch}'] = [record['Version'] for record in records if record.get('Package') == 'bobine']
                for record in records:
                    checksum(path(root / 'debian', record['Filename']), record['SHA256'], record['Size'])

            for arch in ('x86_64', 'aarch64'):
                repo = root / 'fedora' / channel / arch
                repomd = path(repo, 'repodata/repomd.xml')
                signature(repomd, '.asc')
                ns = {'r': 'http://linux.duke.edu/metadata/repo', 'p': 'http://linux.duke.edu/metadata/common'}
                primary = None
                for item in ET.parse(repomd).getroot().findall('r:data', ns):
                    location = path(repo, item.find('r:location', ns).attrib['href'])
                    digest = item.find('r:checksum', ns)
                    if digest.attrib['type'] != 'sha256':
                        raise ValueError('algorithme DNF non pris en charge')
                    checksum(location, digest.text, item.findtext('r:size', namespaces=ns))
                    if item.attrib['type'] == 'primary':
                        primary = location
                if primary is None:
                    raise ValueError(f'index DNF primary absent : {repo}')
                with gzip.open(primary) as stream:
                    packages = ET.parse(stream).getroot().findall('p:package', ns)
                if not packages:
                    raise ValueError(f'index DNF vide : {repo}')
                versions[f'dnf/{channel}/{arch}'] = []
                for item in packages:
                    digest = item.find('p:checksum', ns)
                    if digest.attrib['type'] != 'sha256':
                        raise ValueError('algorithme RPM non pris en charge')
                    checksum(path(repo, item.find('p:location', ns).attrib['href']), digest.text,
                             item.find('p:size', ns).attrib['package'])
                    version = item.find('p:version', ns).attrib
                    versions[f'dnf/{channel}/{arch}'].append(f"{version['ver']}-{version['rel']}")

                repo = root / 'arch' / channel / arch
                for index in ('bobine.db', 'bobine.db.tar.gz', 'bobine.files', 'bobine.files.tar.gz'):
                    signature(path(repo, index), '.sig')
                found = []
                with tarfile.open(path(repo, 'bobine.db')) as archive:
                    for member in archive:
                        if not member.name.endswith('/desc'):
                            continue
                        text = archive.extractfile(member).read().decode()
                        values = dict(re.findall(r'%([A-Z0-9]+)%\n([^\n]+)', text))
                        package = path(repo, values['FILENAME'])
                        checksum(package, values['SHA256SUM'], values['CSIZE'])
                        signature(package, '.sig')
                        found.append(values['VERSION'])
                if not found:
                    raise ValueError(f'index Pacman vide : {repo}')
                versions[f'pacman/{channel}/{arch}'] = found
    stable = bobine.get('stable/amd64', [])
    if len(set(stable)) != 1 or stable != bobine.get('stable/arm64'):
        raise ValueError('versions stables APT incohérentes entre architectures')
    (root / 'mirror-packages.json').write_text(json.dumps({'verified_at': int(time.time()), 'versions': versions}, indent=2) + '\n')
    (root / 'latest.json').write_text(json.dumps({'version': stable[0]}) + '\n')
    print(json.dumps(versions, indent=2))


if __name__ == '__main__':
    try:
        verify(Path(sys.argv[1]))
    except (ValueError, KeyError, IndexError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(f'Vérification des paquets refusée : {error}')

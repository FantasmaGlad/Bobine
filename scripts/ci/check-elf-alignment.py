#!/usr/bin/env python3
"""Contrôle l'alignement sur 16 Kio des segments LOAD des bibliothèques natives Android."""
from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath

PAGE = 16384
PT_LOAD = 1


def load_alignments(data: bytes) -> list[int]:
    """`p_align` de chaque segment PT_LOAD d'un ELF (little-endian, 32 ou 64 bits)."""
    if data[:4] != b"\x7fELF":
        raise ValueError("pas un fichier ELF")
    if data[5] != 1:
        raise ValueError("ELF big-endian non pris en charge")
    if data[4] == 2:
        phoff, = struct.unpack_from("<Q", data, 0x20)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x36)
        fmt = "<IIQQQQQQ"
    elif data[4] == 1:
        phoff, = struct.unpack_from("<I", data, 0x1C)
        phentsize, phnum = struct.unpack_from("<HH", data, 0x2A)
        fmt = "<IIIIIIII"
    else:
        raise ValueError("classe ELF inconnue")
    aligns = []
    for index in range(phnum):
        fields = struct.unpack_from(fmt, data, phoff + index * phentsize)
        if fields[0] == PT_LOAD:
            aligns.append(fields[-1])
    if not aligns:
        raise ValueError("aucun segment PT_LOAD")
    return aligns


def is_aligned(aligns: list[int]) -> bool:
    return all(a >= PAGE and a % PAGE == 0 for a in aligns)


def libraries_of_apk(apk: Path):
    """(abi, nom, contenu) de chaque lib/<abi>/*.so de l'APK."""
    with zipfile.ZipFile(apk) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) == 3 and parts[0] == "lib" and ".so" in parts[2]:
                yield parts[1], parts[2], archive.read(info)


def libraries_of_dir(root: Path):
    for path in sorted(root.glob("*/*")):
        if path.is_file() and ".so" in path.name:
            yield path.parent.name, path.name, path.read_bytes()


def check(libraries, enforced: set[str]) -> int:
    failures = counted = 0
    for abi, name, data in libraries:
        counted += 1
        try:
            aligns = load_alignments(data)
        except ValueError as exc:
            print(f"::error::{abi}/{name} : {exc}")
            failures += 1
            continue
        if is_aligned(aligns):
            print(f"{abi}/{name} : LOAD alignés sur 16 Kio")
        elif abi in enforced:
            print(f"::error::{abi}/{name} : segment LOAD aligné sur {min(aligns)} octets (16384 requis)")
            failures += 1
        else:
            print(f"::notice::{abi}/{name} : LOAD aligné sur {min(aligns)} octets, ABI non concernée par les pages de 16 Kio")
    if not counted:
        print("::error::aucune bibliothèque native trouvée")
        return 1
    return 1 if failures else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--apk", type=Path)
    source.add_argument("--dir", type=Path)
    parser.add_argument("--enforce-abi", action="append", default=None)
    args = parser.parse_args(argv)
    enforced = set(args.enforce_abi or ["arm64-v8a"])
    libraries = libraries_of_apk(args.apk) if args.apk else libraries_of_dir(args.dir)
    return check(libraries, enforced)


if __name__ == "__main__":
    sys.exit(main())

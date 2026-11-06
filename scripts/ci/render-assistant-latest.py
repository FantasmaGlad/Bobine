#!/usr/bin/env python3
"""Écrit `latest.json`, le manifeste que lit la mise à jour automatique de l'assistant (greffon updater de Tauri).

Usage : render-assistant-latest.py <dossier des assets> <tag de la release de l'assistant> <version>
  ex. render-assistant-latest.py assistant-assets assistant-canary 5.1.1+canary.412

Une entrée par paquet que l'assistant installe lui-même, avec le contenu de sa signature `.sig` : le greffon cherche
`<os>-<arch>-<installeur>` puis `<os>-<arch>`, d'où les clés `linux-x86_64-deb` et `linux-x86_64-rpm`.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOSITORY = "FantasmaGlad/Bobine"
# Clé du greffon -> motif du paquet publié (cf. assistant/scripts/bundle.py).
PLATFORMS = {
    "windows-x86_64": "Bobine-Assistant-Setup-{s}.exe",
    "windows-aarch64": "Bobine-Assistant-Setup-{s}-arm64.exe",
    "darwin-aarch64": "Bobine-Assistant-{s}-arm64.app.tar.gz",
    "linux-x86_64-deb": "bobine-assistant_{s}_amd64.deb",
    "linux-x86_64-rpm": "bobine-assistant-{s}.x86_64.rpm",
    "linux-aarch64-deb": "bobine-assistant_{s}_arm64.deb",
    "linux-aarch64-rpm": "bobine-assistant-{s}.aarch64.rpm",
}


def suffix_of(directory: Path) -> str:
    """Suffixe des noms de fichiers (5.1.1, beta ou canary), lu sur l'installeur Windows."""
    found = sorted(p for p in directory.glob("Bobine-Assistant-Setup-*.exe") if not p.name.endswith("-arm64.exe"))
    if len(found) != 1:
        raise SystemExit(f"installeur Windows de l'assistant introuvable ou multiple dans {directory}")
    return found[0].name.removeprefix("Bobine-Assistant-Setup-").removesuffix(".exe")


def manifest(directory: Path, tag: str, version: str, now: datetime | None = None) -> dict:
    suffix = suffix_of(directory)
    base = f"https://github.com/{REPOSITORY}/releases/download/{tag}"
    platforms = {}
    for key, pattern in PLATFORMS.items():
        name = pattern.format(s=suffix)
        signature = directory / f"{name}.sig"
        if not (directory / name).is_file() or not signature.is_file():
            raise SystemExit(f"{name} ou sa signature manquant dans {directory}")
        platforms[key] = {"url": f"{base}/{name}", "signature": signature.read_text(encoding="utf-8").strip()}
    published = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    return {
        "version": version,
        "notes": f"https://github.com/{REPOSITORY}/releases/tag/{tag}",
        "pub_date": published.isoformat().replace("+00:00", "Z"),
        "platforms": platforms,
    }


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    directory = Path(sys.argv[1])
    data = manifest(directory, sys.argv[2], sys.argv[3])
    (directory / "latest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"latest.json : {data['version']}, {len(data['platforms'])} plateformes")

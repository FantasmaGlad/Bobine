#!/usr/bin/env python3
"""Notes de la release de l'assistant d'installation pour un canal (Markdown sur stdout).

Usage : render-assistant-notes.py <canal> <tag de Bobine> <suffixe des fichiers>
  ex. render-assistant-notes.py stable V5.1.1 5.1.1 ; render-assistant-notes.py canary canary canary
"""
from __future__ import annotations

import sys

REPOSITORY = "FantasmaGlad/Bobine"
LABELS = {"stable": "Stable", "beta": "Bêta", "canary": "Canary"}


def render(channel: str, bobine_tag: str, suffix: str) -> str:
    if channel not in LABELS:
        raise SystemExit(f"canal inconnu : {channel}")
    base = f"https://github.com/{REPOSITORY}/releases/download/assistant-{bobine_tag}"

    def link(name: str, text: str) -> str:
        return f"[{text}]({base}/{name})"

    rows = [
        ("**Windows**", f"{link(f'Bobine-Assistant-Setup-{suffix}.exe', 'x64')} · {link(f'Bobine-Assistant-Setup-{suffix}-arm64.exe', 'ARM64')}",
         "installation par utilisateur, sans droits d'administrateur"),
        ("**macOS** Apple Silicon", link(f"Bobine-Assistant-{suffix}-arm64.dmg", f"Bobine-Assistant-{suffix}-arm64.dmg"),
         "signature ad hoc : autoriser l'ouverture au premier lancement"),
        ("**Debian, Ubuntu**", f"{link(f'bobine-assistant_{suffix}_amd64.deb', 'amd64')} · {link(f'bobine-assistant_{suffix}_arm64.deb', 'arm64')}",
         "`sudo apt install ./bobine-assistant_*.deb`"),
        ("**Fedora, RHEL**", f"{link(f'bobine-assistant-{suffix}.x86_64.rpm', 'x86_64')} · {link(f'bobine-assistant-{suffix}.aarch64.rpm', 'aarch64')}",
         "`sudo dnf install ./bobine-assistant-*.rpm`"),
    ]
    lines = [
        f"# Bobine Assistant — {LABELS[channel]}",
        "",
        "L'assistant d'installation découvre un mini PC sur le réseau local, s'y connecte en SSH et y installe l'appliance "
        f"Bobine du canal choisi. Il accompagne la release [Bobine {bobine_tag}](https://github.com/{REPOSITORY}/releases/tag/{bobine_tag}).",
        "",
        "| Système | Fichier | Remarque |",
        "| :--- | :--- | :--- |",
        *[f"| {system} | {file} | {note} |" for system, file, note in rows],
        "",
        "Binaires Linux sans installation (x64 et ARM64) : `bobine-assistant` et `bobine-assistant-arm64` dans la release "
        f"[Bobine {bobine_tag}](https://github.com/{REPOSITORY}/releases/tag/{bobine_tag}).",
        "",
        "## Vérifier les fichiers",
        "",
        "`SHA256SUMS` est signé par la clé des dépôts de paquets de Bobine.",
        "",
        "```bash",
        "curl -fsSL https://packages.bobine.fit/bobine.gpg | gpg --import",
        "gpg --verify SHA256SUMS.asc SHA256SUMS",
        "sha256sum --check --ignore-missing SHA256SUMS",
        "```",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    sys.stdout.write(render(*sys.argv[1:]))

#!/usr/bin/env python3
"""Construit les paquets de l'assistant d'installation (Tauri) pour un canal et les range sous des noms stables.

Usage : bundle.py --channel stable|beta|canary --out DOSSIER [--filename-version 5.1.0|beta|canary] [--version V]

- version du paquet : `--version`, sinon `VERSION` à la racine du dépôt. La CI passe `5.1.1+canary.<n° de run>` pour
  un canal glissant : la mise à jour automatique ne propose qu'une version strictement plus récente (les métadonnées
  de build se comparent numériquement), et RPM refuse le tiret d'une préversion ;
- icônes : celles du canal (`src-tauri/icons/<canal>/`, générées par `scripts/generate_channel_icons.py`) ;
- paquets selon le système : `.deb` et `.rpm` sous Linux, installeur NSIS sous Windows, `.dmg` sous macOS.
  Pas d'AppImage : sa construction télécharge des outils non épinglés ;
- CLI Tauri épinglée (`TAURI_CLI`), même version mineure que la caisse `tauri` du `Cargo.lock` ;
- mise à jour automatique : l'assistant lit `latest.json` dans la release de son canal (`UPDATE_ENDPOINT`). Quand
  `TAURI_SIGNING_PRIVATE_KEY` est fourni (publication, jamais une PR), chaque paquet que l'assistant sait installer
  reçoit sa signature `.sig`, et macOS son archive de mise à jour `.app.tar.gz`. La signature est liée à la version
  (`--app-version`) : `requireSignedVersion` refuse un manifeste qui annoncerait une autre version que celle signée.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TAURI_CLI = "@tauri-apps/cli@2.12.4"
CHANNELS = ("stable", "beta", "canary")
UPDATE_ENDPOINT = "https://github.com/FantasmaGlad/Bobine/releases/download/assistant-{channel}/latest.json"
ASSISTANT = Path(__file__).resolve().parents[1]
REPO = ASSISTANT.parent


def host() -> tuple[str, str]:
    """(système, architecture) au sens des noms de paquets : linux/windows/macos, x64/arm64."""
    system = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}.get(platform.system())
    if system is None:
        raise SystemExit(f"système non pris en charge : {platform.system()}")
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x64" if machine in ("x86_64", "amd64") else None
    if arch is None:
        raise SystemExit(f"architecture non prise en charge : {machine}")
    return system, arch


def bundles_for(system: str) -> list[str]:
    return {"linux": ["deb", "rpm"], "windows": ["nsis"], "macos": ["app", "dmg"]}[system]


def config_override(version: str, channel: str, updater_artifacts: bool = False) -> dict:
    icons = f"icons/{channel}"
    return {
        "version": version,
        "plugins": {"updater": {"endpoints": [UPDATE_ENDPOINT.format(channel=channel)]}},
        "bundle": {
            "createUpdaterArtifacts": updater_artifacts,
            "icon": [f"{icons}/32x32.png", f"{icons}/128x128.png", f"{icons}/128x128@2x.png",
                     f"{icons}/icon.icns", f"{icons}/icon.ico"],
            # Signature ad hoc de toute l'application : sans elle, seul le binaire porte la signature de l'éditeur de
            # liens et `codesign --verify --strict` refuse le bundle.
            "macOS": {"signingIdentity": "-"},
        },
    }


def target_names(system: str, arch: str, filename_version: str) -> dict[str, str]:
    """Extension produite par Tauri -> nom publié."""
    linux_arch = {"x64": ("amd64", "x86_64"), "arm64": ("arm64", "aarch64")}[arch]
    suffix = "" if arch == "x64" else "-arm64"
    return {
        "linux": {
            ".deb": f"bobine-assistant_{filename_version}_{linux_arch[0]}.deb",
            ".rpm": f"bobine-assistant-{filename_version}.{linux_arch[1]}.rpm",
        },
        "windows": {".exe": f"Bobine-Assistant-Setup-{filename_version}{suffix}.exe"},
        "macos": {".dmg": f"Bobine-Assistant-{filename_version}{suffix}.dmg"},
    }[system]


def updater_names(system: str, arch: str, filename_version: str) -> dict[str, str]:
    """Archives que seule la mise à jour automatique utilise (produites avec `createUpdaterArtifacts`)."""
    suffix = "" if arch == "x64" else "-arm64"
    return {".app.tar.gz": f"Bobine-Assistant-{filename_version}{suffix}.app.tar.gz"} if system == "macos" else {}


# Paquets que l'assistant installe lui-même lors d'une mise à jour : chacun reçoit sa signature `.sig`.
SIGNED_EXTENSIONS = (".exe", ".deb", ".rpm", ".app.tar.gz")


def collect(bundle_dir: Path, names: dict[str, str], out: Path) -> list[Path]:
    """Copie chaque paquet produit sous son nom publié ; exactement un paquet par extension attendue."""
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for extension, name in names.items():
        found = [p for p in bundle_dir.rglob(f"*{extension}") if p.is_file()]
        if len(found) != 1:
            raise SystemExit(f"{extension} : {len(found)} paquet(s) produit(s) dans {bundle_dir}, 1 attendu")
        target = out / name
        shutil.copy2(found[0], target)
        written.append(target)
    return written


def gpg_sign_rpm(paths: list[Path], fingerprint: str) -> None:
    """Signe les `.rpm` en OpenPGP (exigé par DNF dans packages.bobine.fit) AVANT leur signature de mise à jour : le même
    fichier sert à la release et au dépôt. Même commande que `scripts/ci/sign-linux-packages.sh` pour Bobine."""
    gpg = shutil.which("gpg")
    for path in paths:
        if path.suffix != ".rpm":
            continue
        subprocess.run(["rpmsign", "--define", f"_gpg_name {fingerprint}", "--define", f"_openpgp_sign_id {fingerprint}",
                        "--define", f"__gpg {gpg}", "--addsign", str(path)], check=True)
        check = subprocess.run(["rpmkeys", "--checksig", str(path)], check=True, capture_output=True, text=True).stdout
        if "digests signatures OK" not in check:
            raise SystemExit(f"signature OpenPGP invalide pour {path.name} : {check.strip()}")


def sign(paths: list[Path], npx: str, version: str) -> None:
    """Signe chaque paquet avec la clé de mise à jour, en liant la signature à `version`.

    `tauri build` signe déjà les artefacts de mise à jour avec la version, mais ce script les recopie puis les signe
    de nouveau : sans `--app-version`, la signature publiée ne porterait plus la version et `requireSignedVersion` ne
    pourrait pas être activé.
    """
    for path in paths:
        if path.name.endswith(SIGNED_EXTENSIONS):
            subprocess.run(
                [npx, "--yes", TAURI_CLI, "signer", "sign", "--app-version", version, str(path)],
                check=True,
            )
            if not path.with_name(path.name + ".sig").is_file():
                raise SystemExit(f"signature absente pour {path.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--channel", choices=CHANNELS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--filename-version", help="version dans les noms de fichiers (défaut : VERSION, ou le canal)")
    parser.add_argument("--version", help="version du paquet (défaut : VERSION)")
    parser.add_argument("--gpg-sign", metavar="EMPREINTE", help="signer les .rpm avec cette clé OpenPGP (déjà importée)")
    args = parser.parse_args(argv)

    version = args.version or (REPO / "VERSION").read_text(encoding="utf-8").strip()
    signing = bool(os.environ.get("TAURI_SIGNING_PRIVATE_KEY"))
    filename_version = args.filename_version or (version if args.channel == "stable" else args.channel)
    system, arch = host()
    bundle_dir = ASSISTANT / "target" / "release" / "bundle"
    shutil.rmtree(bundle_dir, ignore_errors=True)
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx is None:
        raise SystemExit("npx introuvable : Node.js est requis pour la CLI Tauri")

    with tempfile.TemporaryDirectory() as tmp:
        override = Path(tmp) / "canal.json"
        override.write_text(json.dumps(config_override(version, args.channel, signing)), encoding="utf-8")
        command = [npx, "--yes", TAURI_CLI, "build", "--bundles", ",".join(bundles_for(system)), "--config", str(override)]
        print("+", " ".join(command), flush=True)
        subprocess.run(command, cwd=ASSISTANT / "src-tauri", check=True)

    names = target_names(system, arch, filename_version) | (updater_names(system, arch, filename_version) if signing else {})
    written = collect(bundle_dir, names, args.out)
    if args.gpg_sign:
        gpg_sign_rpm(written, args.gpg_sign)
    if signing:
        sign(written, npx, version)
    for path in sorted(args.out.iterdir()):
        print(f"{path.name} ({path.stat().st_size / 1_048_576:.1f} Mio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

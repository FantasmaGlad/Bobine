#!/usr/bin/env python3
"""Construit l'APK Android de l'assistant d'installation pour un canal.

Usage : build_android.py --channel stable|beta|canary --version-code N --out DOSSIER [--filename-version 5.1.0|beta|canary]
        [--version V]

- une seule APK pour ARM64, ARM 32 bits (téléviseurs, anciens téléphones) et x86_64 (émulateurs, Chromebook) ;
- icônes du canal (`src-tauri/icons/<canal>/icon.png`), déclinées pour Android par la CLI Tauri ;
- `--version-code` : entier strictement croissant d'une publication à l'autre, qu'Android exige pour une mise à jour ;
- signature : clé Android de Bobine si `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` et
  `ANDROID_KEY_PASSWORD` sont définies, sinon APK non signée ;
- OpenSSL (pour libssh2) se compile avec le NDK : `NDK_HOME` doit pointer vers lui.

Nom publié : `Bobine-Assistant-<version>.apk`. Pas de mise à jour intégrée sur Android : l'APK se remplace par la
suivante, comme toute application installée hors magasin.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from bundle import ASSISTANT, CHANNELS, REPO, TAURI_CLI

TARGETS = ("aarch64", "armv7", "x86_64")
RES = ASSISTANT / "src-tauri" / "gen" / "android" / "app" / "src" / "main" / "res"
SIGNING_ENV = ("ANDROID_KEYSTORE_PATH", "ANDROID_KEYSTORE_PASSWORD", "ANDROID_KEY_ALIAS", "ANDROID_KEY_PASSWORD")


def toolchain_env() -> dict[str, str]:
    """Outils LLVM du NDK : OpenSSL cherche `ranlib`, que les NDK récents ne fournissent plus sous l'ancien nom."""
    ndk = os.environ.get("NDK_HOME")
    if not ndk:
        raise SystemExit("NDK_HOME non défini : le NDK Android est requis")
    bin_dir = Path(ndk) / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    if not bin_dir.is_dir():
        raise SystemExit(f"outils LLVM du NDK introuvables : {bin_dir}")
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["RANLIB"] = str(bin_dir / "llvm-ranlib")
    return env


def channel_icons(npx: str, channel: str) -> None:
    """Remplace les icônes du lanceur par celles du canal."""
    source = ASSISTANT / "src-tauri" / "icons" / channel / "icon.png"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([npx, "--yes", TAURI_CLI, "icon", str(source), "--output", tmp],
                       cwd=ASSISTANT / "src-tauri", check=True)
        shutil.copytree(Path(tmp) / "android", RES, dirs_exist_ok=True)


def build_tools() -> Path:
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        raise SystemExit("ANDROID_HOME non défini")
    versions = sorted((Path(sdk) / "build-tools").iterdir(), key=lambda p: [int(x) for x in p.name.split(".") if x.isdigit()])
    if not versions:
        raise SystemExit("aucun build-tools dans le SDK Android")
    return versions[-1]


def sign(unsigned: Path, out: Path) -> None:
    tools = build_tools()
    aligned = out.with_suffix(".aligned.apk")
    subprocess.run([str(tools / "zipalign"), "-f", "-P", "16", "4", str(unsigned), str(aligned)], check=True)
    subprocess.run([str(tools / "apksigner"), "sign",
                    "--ks", os.environ["ANDROID_KEYSTORE_PATH"],
                    "--ks-pass", "env:ANDROID_KEYSTORE_PASSWORD",
                    "--ks-key-alias", os.environ["ANDROID_KEY_ALIAS"],
                    "--key-pass", "env:ANDROID_KEY_PASSWORD",
                    # Schéma v4 (`.idsig` à côté) : réservé à l'installation incrémentale par adb, inutile au téléchargement.
                    "--v4-signing-enabled", "false",
                    "--out", str(out), str(aligned)], check=True)
    aligned.unlink()
    subprocess.run([str(tools / "apksigner"), "verify", "--print-certs", str(out)], check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--channel", choices=CHANNELS, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version-code", type=int, required=True)
    parser.add_argument("--filename-version", help="version dans le nom du fichier (défaut : VERSION, ou le canal)")
    parser.add_argument("--version", help="version affichée (défaut : VERSION)")
    args = parser.parse_args(argv)

    version = args.version or (REPO / "VERSION").read_text(encoding="utf-8").strip()
    filename_version = args.filename_version or (version if args.channel == "stable" else args.channel)
    npx = shutil.which("npx")
    if npx is None:
        raise SystemExit("npx introuvable : Node.js est requis pour la CLI Tauri")
    signing = all(os.environ.get(name) for name in SIGNING_ENV)
    if any(os.environ.get(name) for name in SIGNING_ENV) and not signing:
        raise SystemExit("signature Android partielle : les quatre variables ANDROID_* sont requises ensemble")

    channel_icons(npx, args.channel)
    override = {"version": version.split("+")[0], "bundle": {"android": {"versionCode": args.version_code}}}
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "android.json"
        config.write_text(json.dumps(override), encoding="utf-8")
        command = [npx, "--yes", TAURI_CLI, "android", "build", "--ci", "--apk", "--target", *TARGETS,
                   "--config", str(config)]
        print("+", " ".join(command), flush=True)
        subprocess.run(command, cwd=ASSISTANT / "src-tauri", env=toolchain_env(), check=True)

    produced = ASSISTANT / "src-tauri" / "gen" / "android" / "app" / "build" / "outputs" / "apk" / "universal" / "release"
    unsigned = next(produced.glob("*.apk"), None)
    if unsigned is None:
        raise SystemExit(f"aucune APK produite dans {produced}")
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"Bobine-Assistant-{filename_version}.apk"
    if signing:
        sign(unsigned, target)
    else:
        shutil.copy2(unsigned, target)
        print("APK non signée : variables ANDROID_* absentes", flush=True)
    print(f"{target.name} ({target.stat().st_size / 1_048_576:.1f} Mio)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

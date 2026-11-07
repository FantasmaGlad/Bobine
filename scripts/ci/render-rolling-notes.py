#!/usr/bin/env python3
"""Render the download and installation sections of the rolling release notes (canary, beta).

One source for both channels: the same platforms, architectures and installation methods as the
README and the Stable release, with the fixed asset names that scripts/ci/verify-release-assets.sh
requires. The release jobs append the result to the channel introduction, then add the changelog.

Usage: render-rolling-notes.py <canary|beta> [--without-manifests]
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_channel_notes", ROOT / "backend/app/release_channel.py")
registry = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = registry
SPEC.loader.exec_module(registry)

REPOSITORY = "FantasmaGlad/Bobine"
PACKAGES = "https://packages.bobine.fit"
SIGNING_FINGERPRINT = "B77D96D72F84F36ACAA3F8729CBF497D829EE15A"
LABELS = {"canary": "Canary", "beta": "Bêta"}


def glibc_floor() -> str:
    """Plancher de glibc annoncé des paquets (packaging/common/MIN_GLIBC) ; valeur courante tant que ce fichier n'existe pas."""
    path = ROOT / "packaging/common/MIN_GLIBC"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "2.38"


ASSETS = f"https://raw.githubusercontent.com/{REPOSITORY}/main/Assets"


def logo(path: str, alt: str) -> str:
    """Logo officiel servi par le dépôt (même source que le README)."""
    return f'<img src="{ASSETS}/{path}" width="20" height="20" valign="middle" alt="{alt}">'


FAMILIES = """\
## Distributions Linux et méthodes d'installation

Dépôts signés GPG de [packages.bobine.fit](https://packages.bobine.fit), canal @L@ : les mises à jour arrivent par le gestionnaire de paquets de la distribution.

Les binaires exigent **glibc @G@ ou plus récente** : Debian 12, Ubuntu 22.04 LTS et RHEL 9 (et dérivés) ne sont pas pris en charge. La CI installe les paquets sur Ubuntu 24.04 (x86-64 et ARM64), Fedora et Arch Linux (x86-64) ; les autres distributions utilisent les mêmes paquets et ne sont pas testées séparément.

| Famille | Distributions | Dépôt du canal @L@ |
| :--- | :--- | :--- |
| Debian · APT | Debian 13+, Ubuntu 24.04+, Linux Mint, Pop!_OS, Zorin OS, Raspberry Pi OS | `packages.bobine.fit/debian/`, suite `@C@` (amd64, arm64) |
| Fedora · DNF | Fedora, Nobara ; RHEL, AlmaLinux, Rocky Linux 10+ (non testés en CI) | `packages.bobine.fit/fedora/bobine-@C@.repo` (x86_64, aarch64) |
| Arch · pacman | Arch Linux et Arch Linux ARM, EndeavourOS, CachyOS, Manjaro | `packages.bobine.fit/arch/@C@/$arch` (x86_64, aarch64) |

### Installer depuis le dépôt (méthode recommandée)

- **Debian 13+, Ubuntu 24.04+, Linux Mint, Pop!_OS, Zorin OS (APT)** :
  ```bash
  curl -fsSL https://packages.bobine.fit/bobine.gpg | sudo gpg --dearmor -o /etc/apt/keyrings/bobine.gpg
  echo "deb [signed-by=/etc/apt/keyrings/bobine.gpg] https://packages.bobine.fit/debian/ @C@ main" | sudo tee /etc/apt/sources.list.d/bobine.list
  sudo apt update && sudo apt install bobine
  ```
- **Fedora, Nobara, RHEL 10+, AlmaLinux 10+, Rocky Linux 10+ (DNF)** :
  ```bash
  sudo rpm --import https://packages.bobine.fit/bobine.gpg
  # Fedora 41+ (DNF 5)
  sudo dnf config-manager addrepo --from-repofile=https://packages.bobine.fit/fedora/bobine-@C@.repo
  # Fedora 40 et antérieures, famille RHEL (DNF 4) : sudo dnf config-manager --add-repo https://packages.bobine.fit/fedora/bobine-@C@.repo
  sudo dnf install bobine
  ```
- **Arch Linux, EndeavourOS, CachyOS, Manjaro (pacman)** :
  ```bash
  curl -fsSL https://packages.bobine.fit/bobine.gpg | sudo pacman-key --add -
  sudo pacman-key --lsign-key @FINGERPRINT@
  printf '\\n[bobine]\\nServer = https://packages.bobine.fit/arch/@C@/$arch\\n' | sudo tee -a /etc/pacman.conf
  sudo pacman -Syu bobine
  ```

### Installer un paquet autonome (hors ligne)

Téléchargez le paquet de votre architecture dans le tableau ci-dessus, puis :

```bash
sudo apt install ./bobine_@C@_amd64.deb
sudo dnf install ./bobine-@C@.x86_64.rpm
sudo pacman -U ./bobine-@C@-x86_64.pkg.tar.zst
```
"""

INTEGRITY = """\

### Vérifier l'intégrité des fichiers téléchargés

`SHA256SUMS` liste l'empreinte de chaque fichier de la release ; `SHA256SUMS.asc` en est la signature détachée, faite avec la clé qui signe aussi les dépôts de paquets (empreinte `@SPACED@`).

```bash
curl -fsSL https://packages.bobine.fit/bobine.gpg | gpg --import
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum --check --ignore-missing SHA256SUMS
```
"""


def render(channel: str, manifests: bool = True) -> str:
    """Markdown of the download table and the installation sections for a rolling channel."""
    entry = registry.get(channel)
    if entry is None or not entry.rolling:
        raise ValueError(f"not a rolling channel: {channel}")
    label = LABELS[channel]
    base = f"https://github.com/{REPOSITORY}/releases/download/{channel}"

    def link(name: str, text: str | None = None) -> str:
        return f"[**{text or name}**]({base}/{name})"

    def short(name: str, text: str) -> str:
        return f"[{text}]({base}/{name})"

    rows = [
        (logo("Icons/os/windows.svg", "Windows"), "**Windows** 10, 11",
         f"{short(f'Bobine-Setup-{channel}.exe', 'x64')} · {short(f'Bobine-Setup-{channel}-arm64.exe', 'ARM64')}"
         f" · {short('install.ps1', 'install.ps1')}", "installeur `.exe`, Snapdragon pris en charge"),
        (logo("Icons/os/apple.svg", "macOS"), "**macOS**", short(f"Bobine-{channel}.dmg", "Apple Silicon"), "M1 ou plus récent"),
        (logo("Icons/distros/debian.svg", "Debian"), "**Debian, Ubuntu**",
         f"[APT]({PACKAGES}/debian/) · {short(f'bobine_{channel}_amd64.deb', 'amd64')} · {short(f'bobine_{channel}_arm64.deb', 'arm64')}",
         "glibc @G@+"),
        (logo("Icons/distros/fedora.svg", "Fedora"), "**Fedora, RHEL**",
         f"[DNF]({PACKAGES}/fedora/) · {short(f'bobine-{channel}.x86_64.rpm', 'x86_64')} · {short(f'bobine-{channel}.aarch64.rpm', 'aarch64')}",
         "glibc @G@+"),
        (logo("Icons/distros/arch.svg", "Arch Linux"), "**Arch Linux**",
         f"[pacman]({PACKAGES}/arch/) · {short(f'bobine-{channel}-x86_64.pkg.tar.zst', 'x86_64')} ({short(f'bobine-{channel}-x86_64.pkg.tar.zst.sig', 'sig')})"
         f" · {short(f'bobine-{channel}-aarch64.pkg.tar.zst', 'aarch64')} ({short(f'bobine-{channel}-aarch64.pkg.tar.zst.sig', 'sig')})",
         "glibc @G@+"),
        (logo("Icons/os/android.svg", "Android"), "**Android**", short(f"Bobine-{channel}.apk", "APK"), "Android 14+, ARM64"),
        (logo("Icons/os/androidtv.svg", "Android TV"), "**Android TV**", short(f"Bobine-TV-{channel}.apk", "APK TV"), "ARM 32 et 64 bits"),
        (logo("Images/bash.svg", "Mini PC"), "**Mini PC dédié**",
         f"{short('install.sh', 'install.sh')} · [Bobine Deploy](https://github.com/FantasmaGlad/bobine-deploy/releases/latest)",
         f"Debian 13 ; `sudo ./install.sh --channel={channel}`"),
    ]
    if manifests:
        rows.append(("", "**Intégrité**", f"{short('SHA256SUMS', 'SHA256SUMS')} · {short('SHA256SUMS.asc', 'signature')}",
                     "voir plus bas"))

    lines = ["## Téléchargement", "", f"Canal {label}. Commandes en une ligne, y compris par Tor : [README](https://github.com/{REPOSITORY}/blob/main/README.fr.md#installation-en-une-commande).", "",
             "| Plateforme | Fichiers | Prérequis |", "| :--- | :--- | :--- |"]
    lines += [f"| {icon + ' ' if icon else ''}{platform} | {links} | {need} |" for icon, platform, links, need in rows]
    text = "\n".join(lines) + "\n\n" + FAMILIES
    if manifests:
        text += INTEGRITY
    spaced = " ".join(SIGNING_FINGERPRINT[i:i + 4] for i in range(0, 40, 4))
    return (text.replace("@C@", channel).replace("@L@", label).replace("@G@", glibc_floor())
            .replace("@FINGERPRINT@", SIGNING_FINGERPRINT).replace("@SPACED@", spaced))


def main(argv: list[str]) -> int:
    arguments = [a for a in argv if not a.startswith("--")]
    if len(arguments) != 1 or set(argv) - {arguments[0], "--without-manifests"}:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    try:
        sys.stdout.write(render(arguments[0], manifests="--without-manifests" not in argv))
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

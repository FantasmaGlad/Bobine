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


def badge(label: str, logo: str, color: str = "white") -> str:
    return f"![](https://img.shields.io/badge/{label}?style=flat-square&logo={logo}&logoColor={color})"


DEBIAN_FAMILY = " ".join([badge("Debian-A81D33", "debian"), badge("Ubuntu-E95420", "ubuntu"),
                          badge("Linux%20Mint-386D20", "linuxmint"), badge("Pop%21__OS-287D86", "popos"),
                          badge("Zorin%20OS-0969A2", "zorin")])
RPM_FAMILY = " ".join([badge("Fedora-294172", "fedora"), badge("Nobara-303030", "nobaralinux")])
ARCH_FAMILY = " ".join([badge("Arch%20Linux-126B96", "archlinux"), badge("EndeavourOS-5540A5", "endeavouros"),
                        badge("CachyOS-006655", "cachyos"), badge("Manjaro-176D49", "manjaro")])

FAMILIES = """\
## Distributions Linux et méthodes d'installation

Dépôts signés GPG de [packages.bobine.fit](https://packages.bobine.fit), canal @L@ : les mises à jour arrivent par le gestionnaire de paquets de la distribution.

Les binaires exigent **glibc @G@ ou plus récente** : Debian 12, Ubuntu 22.04 LTS et RHEL 9 (et dérivés) ne sont pas pris en charge. La CI installe les paquets sur Ubuntu 24.04 (x86-64 et ARM64), Fedora et Arch Linux (x86-64) ; les autres distributions utilisent les mêmes paquets et ne sont pas testées séparément.

| Famille | Distributions | Format et gestionnaire | Dépôt du canal | Architectures |
| :--- | :--- | :---: | :--- | :---: |
| Debian et dérivés | Debian 13 et plus récent, Ubuntu 24.04 LTS et plus récent, Linux Mint, Pop!_OS, Zorin OS et Raspberry Pi OS basés sur ces versions | `.deb` · APT | `https://packages.bobine.fit/debian/`, suite `@C@` | `amd64`, `arm64` |
| Fedora et dérivés RPM | Fedora, Nobara ; RHEL, AlmaLinux et Rocky Linux 10 et plus récent (non testés en CI) | `.rpm` · DNF | `https://packages.bobine.fit/fedora/bobine-@C@.repo` | `x86_64`, `aarch64` |
| Arch Linux et dérivés | Arch Linux (et Arch Linux ARM), EndeavourOS, CachyOS, Manjaro | `.pkg.tar.zst` · pacman | `https://packages.bobine.fit/arch/@C@/$arch` | `x86_64`, `aarch64` |

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

    debs = [f"bobine_{channel}_amd64.deb", f"bobine_{channel}_arm64.deb"]
    rpms = [f"bobine-{channel}.x86_64.rpm", f"bobine-{channel}.aarch64.rpm"]
    archs = [f"bobine-{channel}-x86_64.pkg.tar.zst", f"bobine-{channel}-aarch64.pkg.tar.zst"]
    rows = [
        (badge("Android_TV-009688", "android"), "`.apk`", "ARM 32 & 64 bits<br>*(armeabi-v7a, arm64-v8a)*",
         link(f"Bobine-TV-{channel}.apk")),
        (badge("Android-3DDC84", "android"), "`.apk`", "ARM64<br>*(arm64-v8a)*", link(f"Bobine-{channel}.apk")),
        (badge("Windows_11-0078D4", "windows11"), "`.exe`", "x86-64 & ARM64<br>*(Intel, AMD, Snapdragon X)*",
         f"{link(f'Bobine-Setup-{channel}.exe')} (x86-64)<br>{link(f'Bobine-Setup-{channel}-arm64.exe')} (ARM64)"),
        (DEBIAN_FAMILY, "`.deb` (APT)", "x86-64 *(amd64)*<br>& ARM64 *(arm64)*",
         f"[**Dépôt APT, canal {label}**]({PACKAGES}/debian/)<br>{link(debs[0])}<br>{link(debs[1])}"),
        (RPM_FAMILY, "`.rpm` (DNF)", "x86-64 *(x86_64)*<br>& ARM64 *(aarch64)*",
         f"[**Dépôt DNF, canal {label}**]({PACKAGES}/fedora/)<br>{link(rpms[0])}<br>{link(rpms[1])}"),
        (ARCH_FAMILY, "`.pkg.tar.zst` (pacman)", "x86-64 *(x86_64)*<br>& ARM64 *(aarch64)*",
         f"[**Dépôt pacman, canal {label}**]({PACKAGES}/arch/)"
         + "".join(f"<br>{link(name)} ([signature]({base}/{name}.sig))" for name in archs)),
        (badge("macOS-000000", "apple"), "`.dmg`", "Apple Silicon *(M1-M4)*", link(f"Bobine-{channel}.dmg")),
        (badge("Bobine%20Assistant-FFC131", "tauri", "black"), "Binaire natif", "x86-64 & ARM64<br>*(Linux)*",
         f"{link('bobine-assistant')} (x86-64)<br>{link('bobine-assistant-arm64')} (ARM64)"),
        (badge("Bash_CLI-4EAA25", "gnubash"), "Script", "x86-64 & ARM64",
         f"{link('install.sh')}<br>ou `sudo ./install.sh --channel={channel}` sur une installation existante"),
    ]
    if manifests:
        rows.append(("Intégrité", "Manifeste signé", "Tous les fichiers",
                     f"{link('SHA256SUMS')}<br>{link('SHA256SUMS.asc', 'SHA256SUMS.asc (signature GPG)')}"))

    lines = ["## Téléchargement", "",
             "| Plateforme & environnement | Format | Architecture | Téléchargement direct & dépôts |",
             "| :--- | :---: | :---: | :--- |"]
    lines += [f"| {platform} | <sub>{fmt}</sub> | <sub>{arch}</sub> | <sub>{links}</sub> |" for platform, fmt, arch, links in rows]
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

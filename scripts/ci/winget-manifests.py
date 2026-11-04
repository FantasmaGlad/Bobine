#!/usr/bin/env python3
"""Manifestes winget d'une release Stable, écrits à partir de son SHA256SUMS. Rien n'est soumis : les fichiers sont
joints à la release, et la demande de fusion vers microsoft/winget-pkgs reste une action du mainteneur.

Usage : winget-manifests.py <SHA256SUMS> <tag Vx.y.z> <dossier de sortie>
"""
import re
import sys
from pathlib import Path

REPO = "FantasmaGlad/Bobine"
IDENTIFIER = "FantasmaGlad.Bobine"
MANIFEST_VERSION = "1.12.0"
DESCRIPTION = "Offline-first video playout for gyms and studios: scheduled classes on screens, projectors and TVs."
DESCRIPTION_FR = "Régie vidéo hors ligne pour salles de sport : cours programmés sur écrans, projecteurs et téléviseurs."


def read_sums(path: Path) -> dict[str, str]:
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](\S+)", line.strip())
        if match:
            sums[match.group(2)] = match.group(1).upper()
    return sums


def manifests(sums: dict[str, str], tag: str) -> dict[str, str]:
    version = tag.removeprefix("V")
    head = f"PackageIdentifier: {IDENTIFIER}\nPackageVersion: {version}\n"
    foot = f"ManifestVersion: {MANIFEST_VERSION}\n"

    def installer(arch: str, name: str) -> str:
        if name not in sums:
            raise SystemExit(f"installeur absent de SHA256SUMS : {name}")
        return (
            f"  - Architecture: {arch}\n"
            f"    InstallerUrl: https://github.com/{REPO}/releases/download/{tag}/{name}\n"
            f"    InstallerSha256: {sums[name]}\n"
        )

    about = (
        "Publisher: FantasmaGlad\nPublisherUrl: https://github.com/FantasmaGlad\nPackageName: Bobine\n"
        f"PackageUrl: https://bobine.fit\nLicense: AGPL-3.0\nLicenseUrl: https://github.com/{REPO}/blob/main/LICENSE\n"
        f"ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/{tag}\n"
    )
    return {
        f"{IDENTIFIER}.yaml": head + "DefaultLocale: en-US\nManifestType: version\n" + foot,
        f"{IDENTIFIER}.installer.yaml": head
        + "InstallerType: inno\nScope: machine\nUpgradeBehavior: install\n"
        + "InstallerSwitches:\n  Silent: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART\n  SilentWithProgress: /SILENT /NORESTART\n"
        + "Installers:\n"
        + installer("x64", f"Bobine-Setup-{version}.exe")
        + installer("arm64", f"Bobine-Setup-{version}-arm64.exe")
        + "ManifestType: installer\n" + foot,
        f"{IDENTIFIER}.locale.en-US.yaml": head + "PackageLocale: en-US\n" + about
        + f"ShortDescription: {DESCRIPTION}\nManifestType: defaultLocale\n" + foot,
        f"{IDENTIFIER}.locale.fr-FR.yaml": head + "PackageLocale: fr-FR\n" + about
        + f"ShortDescription: {DESCRIPTION_FR}\nManifestType: locale\n" + foot,
    }


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    sums_path, tag, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    if not re.fullmatch(r"V\d+\.\d+\.\d+", tag):
        raise SystemExit(f"tag Stable attendu (Vx.y.z) : {tag}")
    out.mkdir(parents=True, exist_ok=True)
    for name, content in manifests(read_sums(sums_path), tag).items():
        (out / name).write_text(content, encoding="utf-8")
    print(f"manifestes winget écrits dans {out}")


if __name__ == "__main__":
    main()

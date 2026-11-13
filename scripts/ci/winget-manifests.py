#!/usr/bin/env python3
"""Manifestes winget d'une release Stable, écrits à partir de son SHA256SUMS ; rien n'est soumis.

Usage : winget-manifests.py <SHA256SUMS> <tag Vx.y.z> <dossier de sortie>
"""
import re
import sys
from pathlib import Path

REPO = "FantasmaGlad/Bobine"
MANIFEST_VERSION = "1.12.0"
PRODUCTS = {
    "bobine": {
        "identifier": "FantasmaGlad.Bobine", "name": "Bobine", "tag": r"V(\d+\.\d+\.\d+)",
        "setup": "Bobine-Setup-{v}{arch}.exe",
        "installer": "InstallerType: inno\nScope: machine\nUpgradeBehavior: install\n"
        "InstallerSwitches:\n  Silent: /VERYSILENT /SUPPRESSMSGBOXES /NORESTART\n  SilentWithProgress: /SILENT /NORESTART\n",
        "en": "Offline-first video playout for gyms and studios: scheduled classes on screens, projectors and TVs.",
        "fr": "Régie vidéo hors ligne pour salles de sport : cours programmés sur écrans, projecteurs et téléviseurs.",
    },
}


def yaml_scalar(value: str) -> str:
    """Guillemets simples YAML : une description contenant « : » reste une chaîne."""
    return "'" + value.replace("'", "''") + "'"


def read_sums(path: Path) -> dict[str, str]:
    sums = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](\S+)", line.strip())
        if match:
            sums[match.group(2)] = match.group(1).upper()
    return sums


def product_of(tag: str) -> tuple[str, str]:
    """(produit, version) d'un tag Stable ; refuse un tag glissant ou inconnu."""
    for product, spec in PRODUCTS.items():
        match = re.fullmatch(spec["tag"], tag)
        if match:
            return product, match.group(1)
    raise SystemExit(f"tag Stable attendu (Vx.y.z) : {tag}")


def manifests(sums: dict[str, str], tag: str) -> dict[str, str]:
    product, version = product_of(tag)
    spec = PRODUCTS[product]
    identifier = spec["identifier"]
    head = f"PackageIdentifier: {identifier}\nPackageVersion: {version}\n"
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
        f"Publisher: FantasmaGlad\nPublisherUrl: https://github.com/FantasmaGlad\nPackageName: {spec['name']}\n"
        f"PackageUrl: https://bobine.fit\nLicense: AGPL-3.0\nLicenseUrl: https://github.com/{REPO}/blob/main/LICENSE\n"
        f"ReleaseNotesUrl: https://github.com/{REPO}/releases/tag/{tag}\n"
    )
    def schema(kind: str) -> str:
        return f"# yaml-language-server: $schema=https://aka.ms/winget-manifest.{kind}.{MANIFEST_VERSION}.schema.json\n\n"

    documents = {
        f"{identifier}.yaml": head + "DefaultLocale: en-US\nManifestType: version\n" + foot,
        f"{identifier}.installer.yaml": head
        + spec["installer"]
        + "Installers:\n"
        + installer("x64", spec["setup"].format(v=version, arch=""))
        + installer("arm64", spec["setup"].format(v=version, arch="-arm64"))
        + "ManifestType: installer\n" + foot,
        f"{identifier}.locale.en-US.yaml": head + "PackageLocale: en-US\n" + about
        + f"ShortDescription: {yaml_scalar(spec['en'])}\nManifestType: defaultLocale\n" + foot,
        f"{identifier}.locale.fr-FR.yaml": head + "PackageLocale: fr-FR\n" + about
        + f"ShortDescription: {yaml_scalar(spec['fr'])}\nManifestType: locale\n" + foot,
    }
    kinds = {
        f"{identifier}.yaml": "version", f"{identifier}.installer.yaml": "installer",
        f"{identifier}.locale.en-US.yaml": "defaultLocale", f"{identifier}.locale.fr-FR.yaml": "locale",
    }
    return {name: schema(kinds[name]) + body for name, body in documents.items()}


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    sums_path, tag, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    product_of(tag)
    out.mkdir(parents=True, exist_ok=True)
    for name, content in manifests(read_sums(sums_path), tag).items():
        (out / name).write_text(content, encoding="utf-8")
    print(f"manifestes winget écrits dans {out}")


if __name__ == "__main__":
    main()

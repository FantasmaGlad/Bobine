"""Choix de l'artefact d'une release selon le profil, la variante et l'architecture."""
from typing import Any


ASSET_EXTENSION_BY_PROFILE = {
    "windows": ".exe",
    "linux-desktop": ".deb",
    "macos": ".dmg",
    "android": ".apk",
}


def asset_matches_variant(name: str, variant: str | None) -> bool:
    """Android publie deux APK par release (`Bobine-<v>.apk` pour téléphone/ tablette, `Bobine-TV-<v>.apk` pour Android TV, `applicationId` différents)."""
    is_tv = "-tv-" in name or name.startswith("bobine-tv")
    return is_tv if variant == "tv" else not is_tv


def detect_cpu_arch() -> str:
    """Normalise l'architecture CPU courante en `'arm64'` ou `'x86_64'`."""
    import os
    import platform

    machine = (os.environ.get("BOBINE_CPU_ARCH") or platform.machine() or "").strip().lower()
    if machine in ("aarch64", "arm64", "armv8l", "armv8b"):
        return "arm64"
    return "x86_64"


def asset_matches_arch(name: str, arch: str) -> bool:
    """Départage les assets multi-architectures (`amd64`/`x86_64` vs `arm64`/`aarch64`)."""
    has_arm = "arm64" in name or "aarch64" in name
    has_x86 = "amd64" in name or "x86_64" in name or "x64" in name
    if arch == "arm64":
        return has_arm
    return has_x86 or not has_arm


def resolve_asset(
    profile: str,
    release_data: dict[str, Any] | None,
    variant: str | None = None,
    arch: str | None = None,
    linux_ext: str | None = None,
) -> dict[str, Any]:
    """Cherche l'asset adapté au profil de déploiement courant parmi ceux d'une release GitHub."""
    if profile == "linux-desktop":
        if linux_ext:
            target_ext = linux_ext
        else:
            from app.utils.deployment_profiles.linux_desktop import detect_linux_package_format

            target_ext = detect_linux_package_format()
    else:
        target_ext = ASSET_EXTENSION_BY_PROFILE.get(profile)

    assets = (release_data or {}).get("assets") or []
    matched = None
    if target_ext:
        candidates = []
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if not name.endswith(target_ext):
                continue
            if profile == "android" and not asset_matches_variant(name, variant):
                continue
            candidates.append(asset)

        if candidates:
            if profile in ("linux-desktop", "windows"):
                effective_arch = arch or detect_cpu_arch()
                for cand in candidates:
                    cname = (cand.get("name") or "").lower()
                    if asset_matches_arch(cname, effective_arch):
                        matched = cand
                        break
                if matched is None and arch is None and len(candidates) == 1:
                    matched = candidates[0]
            else:
                matched = candidates[0]

    return {
        "download_url": matched.get("browser_download_url") if matched else None,
        "asset_name": matched.get("name") if matched else None,
        "asset_size": matched.get("size") if matched else None,
        "asset_digest": matched.get("digest") if matched else None,
    }

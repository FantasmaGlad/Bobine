"""Canaux de diffusion (Stable, Bêta, Canary) : registre et résolution, source UNIQUE."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class ReleaseChannel:
    id: str
    version_suffix: str | None
    release_tag: str | None
    package_order: int | None = None
    arch_suffix: str | None = None

    @property
    def rolling(self) -> bool:
        return self.release_tag is not None


CHANNELS: tuple[ReleaseChannel, ...] = (
    ReleaseChannel(id="stable", version_suffix=None, release_tag=None),
    ReleaseChannel(id="beta", version_suffix="beta", release_tag="beta", package_order=1, arch_suffix="beta"),
    ReleaseChannel(id="canary", version_suffix="canary", release_tag="canary", package_order=0, arch_suffix="alpha"),
)
CHANNEL_IDS: tuple[str, ...] = tuple(channel.id for channel in CHANNELS)
DEFAULT_CHANNEL: str = CHANNELS[0].id
ROLLING_CHANNEL_IDS: tuple[str, ...] = tuple(channel.id for channel in CHANNELS if channel.rolling)

INSTALL_HINT_PATH = Path("/etc/bobine/update-channel")

SourceOfChoice = Literal["user", "install", "locked"]


def get(channel_id: str) -> ReleaseChannel | None:
    return next((channel for channel in CHANNELS if channel.id == channel_id), None)


def normalize(value: object) -> str | None:
    """Identifiant de canal valide (minuscules, sans espaces) ou None."""
    candidate = str(value).strip().lower() if value is not None else ""
    return candidate if candidate in CHANNEL_IDS else None


def _version_pattern() -> re.Pattern[str]:
    suffixes = "|".join(re.escape(c.version_suffix) for c in CHANNELS if c.version_suffix)
    return re.compile(rf"^v?\d+\.\d+\.\d+(?:[-~]({suffixes})|\+({suffixes})\.\d+)$", re.IGNORECASE)


_VERSION_PATTERN = _version_pattern()


def _current_version() -> str:
    from app.utils.version import get_app_version

    return get_app_version()


def rolling_channel_of_version(version: str | None = None) -> str | None:
    """Canal rolling (« beta », « canary ») d'un build d'après le suffixe de sa version, ou None pour une Stable ou un suffixe inconnu."""
    candidate = (version if version is not None else _current_version()).strip()
    match = _VERSION_PATTERN.match(candidate)
    if not match:
        try:
            package = parse_package_version(candidate)
        except ValueError:
            return None
        return package.channel if package.build else None
    suffix = (match.group(1) or match.group(2)).lower()
    return next((c.id for c in CHANNELS if c.version_suffix == suffix), None)


def build_channel_of_version(version: str | None = None) -> str:
    """Canal du build : canal rolling porté par le suffixe de version, sinon la Stable."""
    return rolling_channel_of_version(version) or DEFAULT_CHANNEL


def install_channel(version: str | None = None, hint_file: Path = INSTALL_HINT_PATH) -> str:
    """Canal rejoint à l'installation."""
    rolling = rolling_channel_of_version(version)
    if rolling:
        return rolling
    if not getattr(sys, "frozen", False):
        try:
            hinted = normalize(hint_file.read_text(encoding="utf-8"))
        except OSError:
            hinted = None
        if hinted:
            return hinted
    return DEFAULT_CHANNEL


@dataclass(frozen=True)
class ChannelChoice:
    effective: str
    source: SourceOfChoice
    install: str


def resolve(
    stored: object,
    version: str | None = None,
    hint_file: Path = INSTALL_HINT_PATH,
    locked: str | None = None,
) -> ChannelChoice:
    """Canal effectif à partir de la valeur enregistrée (réglage `update_channel`, absente ou invalide = aucun choix)."""
    install = install_channel(version, hint_file)
    forced = normalize(locked)
    if forced:
        return ChannelChoice(effective=forced, source="locked", install=install)
    chosen = normalize(stored)
    if chosen:
        return ChannelChoice(effective=chosen, source="user", install=install)
    return ChannelChoice(effective=install, source="install", install=install)


@dataclass(frozen=True)
class PackageVersion:
    base: str
    channel: str
    build: str | None

    @property
    def debian(self) -> str:
        if self.build is None:
            return self.base
        return f"{self.base}~{get(self.channel).package_order}.{self.channel}.{self.build}"

    @property
    def rpm_release(self) -> str:
        if self.build is None:
            return "1"
        return f"0.{get(self.channel).package_order + 1}.{self.channel}.{self.build}"

    @property
    def arch_version(self) -> str:
        if self.build is None:
            return self.base
        return f"{self.base}{get(self.channel).arch_suffix}.{self.build}"


_PACKAGE_VERSION = re.compile(r"^(\d+\.\d+\.\d+)(?:\+([a-z]+)\.(\d+)|~(\d+)\.([a-z]+)\.(\d+))?$")


def parse_package_version(version: str) -> PackageVersion:
    """Décompose la version de construction (« 5.0.6 » ou « 5.0.6~0.canary.42 ») en version de base, canal et numéro de build."""
    match = _PACKAGE_VERSION.match(version.strip())
    if not match:
        raise ValueError(f"version de paquet '{version}' non reconnue (attendu x.y.z ou x.y.z~<rang>.<canal>.N)")
    base, legacy_suffix, legacy_build, rank, suffix, build = match.groups()
    suffix, build = suffix or legacy_suffix, build or legacy_build
    if suffix is None:
        return PackageVersion(base=base, channel=DEFAULT_CHANNEL, build=None)
    channel = next((c.id for c in CHANNELS if c.version_suffix == suffix.lower()), None)
    if channel is None:
        raise ValueError(f"version de paquet '{version}' : '{suffix}' n'est pas un canal rolling ({', '.join(ROLLING_CHANNEL_IDS)})")
    if rank is not None and rank != str(get(channel).package_order):
        raise ValueError(f"rang de préversion incohérent pour '{channel}'")
    if int(build) <= 0:
        raise ValueError("le numéro de build doit être strictement positif")
    return PackageVersion(base=base, channel=channel, build=build)


def package_version(base: str, channel: str, build: str | None = None) -> PackageVersion:
    """Une seule traduction des identités produit vers les formats natifs des trois distributions."""
    if not re.fullmatch(r"\d+\.\d+\.\d+", base) or normalize(channel) != channel:
        raise ValueError("version de base ou canal invalide")
    if channel == DEFAULT_CHANNEL:
        return PackageVersion(base, channel, None)
    if build is None or not re.fullmatch(r"[1-9]\d*", str(build)):
        raise ValueError("un build positif est requis pour un canal rolling")
    return PackageVersion(base, channel, str(build))

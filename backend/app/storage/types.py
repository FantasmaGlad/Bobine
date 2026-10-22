"""Types communs du stockage externe (données pures, sans E/S)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

# Natures de support (affichage, règles de longévité).
KINDS = ("usb", "sd", "hdd", "ssd", "image", "other")

_KEY_SAFE = re.compile(r"[^0-9A-Za-z._-]")


@dataclass(frozen=True)
class Volume:
    """Un système de fichiers d'un support amovible, tel que vu par l'inventaire du système."""

    key: str
    device: str  # /dev/sdb1 : jamais exposé au client comme identifiant d'action
    name: str
    fs_uuid: str | None
    label: str | None
    fstype: str | None
    size_bytes: int
    mountpoint: str | None
    mounts: tuple[str, ...] = ()
    mount_options: tuple[str, ...] = ()
    read_only_device: bool = False
    removable: bool = False
    hotplug: bool = False
    transport: str | None = None
    vendor: str | None = None
    model: str | None = None
    serial: str | None = None
    rotational: bool | None = None
    kind: str = "other"
    dev_type: str = "part"
    discard_supported: bool = False
    disk: str | None = None  # nom du disque parent (sdb), sert à la mise en veille / SMART
    sd_card: bool = False

    @property
    def mounted(self) -> bool:
        return bool(self.mountpoint)

    @property
    def mounted_read_only(self) -> bool | None:
        """Vrai si monté en lecture seule, faux si monté en lecture-écriture, None si non monté."""
        if not self.mounted:
            return None
        return self.read_only_device or "ro" in self.mount_options

    @property
    def display_name(self) -> str:
        if self.label:
            return self.label
        parts = [p for p in (self.vendor, self.model) if p]
        return " ".join(parts) if parts else self.name


@dataclass(frozen=True)
class Excluded:
    """Un support que Bobine refuse de proposer, avec la raison (journal, tests)."""

    device: str
    reason: str  # system | internal | bobine_data | unusable_fs | encrypted | swap


@dataclass
class Inventory:
    volumes: list[Volume] = field(default_factory=list)
    excluded: list[Excluded] = field(default_factory=list)
    encrypted: list[Volume] = field(default_factory=list)


def make_key(fs_uuid: str | None, serial: str | None, model: str | None, partn: str | None, size: int) -> str:
    """Clé stable d'un volume : UUID du système de fichiers, sinon empreinte du matériel.

    Le point de montage n'entre jamais dans la clé : il change à chaque branchement."""
    if fs_uuid:
        return "u-" + _KEY_SAFE.sub("_", fs_uuid.strip().lower())
    raw = "|".join([serial or "", model or "", partn or "", str(size)])
    return "d-" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def has_stable_identity(volume: Volume) -> bool:
    """Seul un volume portant un UUID de système de fichiers peut devenir une bibliothèque."""
    return bool(volume.fs_uuid)


def volume_public(volume: Volume) -> dict[str, Any]:
    """Représentation publique : jamais de chemin de périphérique (`/dev/...`) ni de série."""
    return {
        "key": volume.key,
        "name": volume.display_name,
        "label": volume.label,
        "fstype": volume.fstype,
        "size_bytes": volume.size_bytes,
        "kind": volume.kind,
        "transport": volume.transport,
        "vendor": volume.vendor,
        "model": volume.model,
        "rotational": volume.rotational,
        "mounted": volume.mounted,
        "mounted_read_only": volume.mounted_read_only,
        "uuid_known": bool(volume.fs_uuid),
    }

"""Support vu comme un disque entier (données pures) et empreintes d'identité.

Le formatage agit sur le DISQUE (table de partitions GPT + une partition alignée), pas sur une seule partition :
le plan doit donc montrer TOUTES les partitions qui seront effacées, y compris celles que Bobine ne propose
jamais (système de fichiers inconnu, chiffré...)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PartInfo:
    """Un système de fichiers du disque : une partition, ou le disque lui-même s'il n'a pas de table de partitions."""

    name: str
    path: str
    fstype: str | None
    label: str | None
    uuid: str | None
    size_bytes: int
    mountpoints: tuple[str, ...] = ()
    partn: str | None = None
    read_only: bool = False
    start_sectors: int | None = None
    whole_disk: bool = False

    @property
    def mounted(self) -> bool:
        return bool(self.mountpoints)


@dataclass(frozen=True)
class DiskInfo:
    diskseq: str | None = field(default=None, kw_only=True)  # change à chaque reconnexion du disque
    name: str                       # sdb, mmcblk0, loop3
    path: str                       # /dev/sdb : n'est JAMAIS exposé au client
    dev_type: str                   # disk | loop
    size_bytes: int
    vendor: str | None = None
    model: str | None = None
    serial: str | None = None
    transport: str | None = None
    removable: bool = False
    hotplug: bool = False
    read_only: bool = False
    rotational: bool | None = None
    ptable: str | None = None       # gpt | dos | None
    sd_card: bool = False
    kind: str = "other"
    partitions: tuple[PartInfo, ...] = field(default_factory=tuple)

    @property
    def filesystems(self) -> tuple[PartInfo, ...]:
        return tuple(p for p in self.partitions if p.fstype)

    @property
    def mountpoints(self) -> tuple[str, ...]:
        return tuple(m for p in self.partitions for m in p.mountpoints)

    @property
    def display_name(self) -> str:
        for part in self.partitions:
            if part.label:
                return part.label
        parts = [p for p in (self.vendor, self.model) if p]
        return " ".join(parts) if parts else self.name

    @property
    def sector_aligned_first_start(self) -> int | None:
        starts = [p.start_sectors for p in self.partitions if p.start_sectors is not None and not p.whole_disk]
        return min(starts) if starts else None


def identity(disk: DiskInfo) -> dict[str, Any]:
    """Ce qui fait CE support (et pas un autre ayant pris le même nom `/dev/sdX`) : jamais l'état de montage,
    qui change légitimement pendant l'assistant."""
    return {
        "path": disk.path,
        "type": disk.dev_type,
        "diskseq": disk.diskseq,
        "size": disk.size_bytes,
        "vendor": disk.vendor or "",
        "model": disk.model or "",
        "serial": disk.serial or "",
        "transport": disk.transport or "",
        "ptable": disk.ptable or "",
        "parts": [
            [p.partn or "", p.uuid or "", p.fstype or "", p.label or "", p.size_bytes, int(p.whole_disk)]
            for p in sorted(disk.partitions, key=lambda p: (p.partn or "", p.name))
        ],
    }


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def hardware_identity(disk: DiskInfo) -> tuple:
    """Identité physique conservée lors du formatage, y compris la génération de connexion Linux."""
    return (disk.path, disk.dev_type, disk.diskseq, disk.serial, disk.size_bytes, disk.vendor, disk.model, disk.transport)


def fingerprint(disk: DiskInfo) -> str:
    return _digest(identity(disk))


def inventory_digest(disks: list[DiskInfo]) -> str:
    """Empreinte de l'ensemble des supports candidats branchés : un autre support qui apparaît ou disparaît entre le
    plan et l'exécution invalide le plan (les noms `/dev/sdX` peuvent alors avoir été réattribués)."""
    return _digest(sorted([d.path, d.size_bytes, d.serial or "", d.model or "", [p.uuid or "" for p in d.partitions]] for d in disks))


def serial_tail(disk: DiskInfo, n: int = 4) -> str | None:
    cleaned = "".join(c for c in (disk.serial or "") if c.isalnum())
    return cleaned[-n:] if len(cleaned) >= n else (cleaned or None)


@dataclass(frozen=True)
class FormatSpec:
    """Ce que le pilote doit créer : une table GPT, UNE partition alignée sur 1 Mio, un système de fichiers (formatage rapide)."""

    fs: str                     # ext4 | exfat | vfat | ntfs
    label: str
    udisks_type: str
    partition_guid: str
    partition_name: str
    mkfs_args: tuple[str, ...]
    take_ownership: bool
    offset_bytes: int = 1024 * 1024

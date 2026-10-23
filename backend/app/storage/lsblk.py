"""Analyse de `lsblk -J -b` et règles d'exclusion strictes (logique pure, testée sans matériel).

Règle d'or : **un support n'est proposé que s'il est manifestement amovible** (USB, carte SD, disque
hotplug, image disque de données). Tout disque portant un montage système, tout disque interne fixe
et tout volume qui contient ou est contenu dans un dossier de données de Bobine est écarté avant
même d'atteindre l'interface — et chaque action est revalidée contre l'inventaire courant (le client
n'envoie jamais de chemin de périphérique).
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .types import Excluded, Inventory, Volume, make_key

LSBLK_COLUMNS = "NAME,PATH,UUID,LABEL,FSTYPE,SIZE,RM,HOTPLUG,TRAN,MOUNTPOINTS,MODEL,SERIAL,TYPE,RO,ROTA,PKNAME,VENDOR,DISC-GRAN,PARTN"

# Montages dont la présence sur un disque fait de lui un disque système (jamais proposé).
SYSTEM_MOUNTS = ("/", "/boot", "/boot/efi", "/efi", "/home", "/var", "/usr", "/opt", "/srv", "/tmp", "/nix", "/gnu")
SYSTEM_MOUNT_PREFIXES = ("/snap", "/var/lib/snapd", "/sysroot")

# Systèmes de fichiers de données qu'un utilisateur peut raisonnablement brancher.
DATA_FILESYSTEMS = frozenset({
    "vfat", "fat", "fat16", "fat32", "msdos", "exfat", "ntfs", "ntfs3", "ext2", "ext3", "ext4", "btrfs", "xfs",
    "f2fs", "hfsplus", "hfs", "apfs", "udf", "iso9660", "reiserfs", "jfs",
})
# Pour une image loop : jamais les images en lecture seule des snaps/AppImages/ISO.
LOOP_ALLOWED_FILESYSTEMS = DATA_FILESYSTEMS - {"iso9660", "udf"}
_NEVER_LISTED = frozenset({"swap", "squashfs", "erofs", "LVM2_member", "linux_raid_member", "zfs_member", "ceph_bluestore", "bcache"})
_ENCRYPTED = frozenset({"crypto_LUKS", "BitLocker"})

_OCTAL = re.compile(r"\\([0-7]{3})")


def _flag(value: Any) -> bool:
    """Booléen de lsblk : `true`/`false` (récent), `"1"`/`"0"` ou entiers (ancien)."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes")


def _opt_flag(value: Any) -> bool | None:
    return None if value is None else _flag(value)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


@dataclass(frozen=True)
class MountInfo:
    mountpoint: str
    options: frozenset[str]
    fstype: str
    source: str


def parse_mountinfo(text: str) -> list[MountInfo]:
    """Analyse `/proc/self/mountinfo` : options par montage (ro/rw, noatime…) pour chaque point de montage."""
    entries: list[MountInfo] = []
    for line in text.splitlines():
        parts = line.split()
        if "-" not in parts:
            continue
        sep = parts.index("-")
        if sep < 6 or len(parts) < sep + 3:
            continue
        mountpoint = _OCTAL.sub(lambda m: chr(int(m.group(1), 8)), parts[4])
        options = set(parts[5].split(",")) | set(parts[sep + 3].split(",")) if len(parts) > sep + 3 else set(parts[5].split(","))
        entries.append(MountInfo(mountpoint, frozenset(o for o in options if o), parts[sep + 1], parts[sep + 2]))
    return entries


def _mount_options(mountinfo: Iterable[MountInfo], mountpoint: str | None) -> tuple[str, ...]:
    if not mountpoint:
        return ()
    for entry in mountinfo:
        if entry.mountpoint == mountpoint:
            return tuple(sorted(entry.options))
    return ()


def _norm(path: str) -> str:
    return os.path.normpath(path) if path else path


def is_system_mount(mountpoint: str) -> bool:
    m = _norm(mountpoint)
    if m in SYSTEM_MOUNTS:
        return True
    return any(m == p.rstrip("/") or m.startswith(p) for p in SYSTEM_MOUNT_PREFIXES)


def overlaps_protected(mountpoint: str, protected_paths: Iterable[str]) -> bool:
    """Vrai si le point de montage contient un dossier de données de Bobine, est l'un d'eux, ou est monté dedans."""
    m = _norm(mountpoint)
    for raw in protected_paths:
        if not raw:
            continue
        p = _norm(raw)
        if m == p or p.startswith(m.rstrip("/") + "/") or m.startswith(p.rstrip("/") + "/"):
            return True
    return False


def _flatten(node: dict[str, Any]) -> list[dict[str, Any]]:
    out = [node]
    for child in node.get("children") or []:
        out.extend(_flatten(child))
    return out


def _mountpoints(node: dict[str, Any]) -> list[str]:
    raw = node.get("mountpoints")
    if raw is None and node.get("mountpoint"):
        raw = [node.get("mountpoint")]
    return [m for m in (raw or []) if m]


def classify_kind(*, transport: str | None, rotational: bool | None, sd_card: bool, name: str, size: int, dev_type: str) -> str:
    """Nature indicative du support (règles de longévité et icône) ; une clé USB et un SSD USB ne se distinguent pas toujours."""
    if dev_type == "loop":
        return "image"
    if sd_card or name.startswith("mmcblk"):
        return "sd"
    if rotational is True:
        return "hdd"
    if transport == "usb":
        return "ssd" if size >= 200 * 10**9 else "usb"
    if transport in ("sata", "nvme", "ata", "sas"):
        return "ssd"
    return "usb"


def parse_lsblk(
    data: str | dict[str, Any],
    *,
    mountinfo: Iterable[MountInfo] = (),
    protected_paths: Iterable[str] = (),
    is_sd_card: Callable[[str], bool] | None = None,
    include_images: bool = True,
) -> Inventory:
    """Transforme la sortie de lsblk en inventaire de supports proposables + liste des exclusions.

    `is_sd_card(nom_du_disque)` distingue une carte SD d'une mémoire eMMC interne (sysfs, injectable)."""
    payload = json.loads(data) if isinstance(data, str) else data
    mountinfo = list(mountinfo)
    protected = [p for p in protected_paths if p]
    sd_probe = is_sd_card or (lambda _name: False)
    inventory = Inventory()

    for top in payload.get("blockdevices", []):
        top_type = str(top.get("type") or "disk")
        if top_type in ("rom", "ram"):
            continue
        nodes = _flatten(top)
        name = str(top.get("name") or "")
        top_path = str(top.get("path") or f"/dev/{name}")

        def reject(reason: str, only_filesystems: bool = True) -> None:
            for node in nodes:
                if not only_filesystems or node.get("fstype"):
                    inventory.excluded.append(Excluded(str(node.get("path") or node.get("name")), reason))

        if any(m for node in nodes for m in _mountpoints(node) if is_system_mount(m)) or any(
            str(node.get("fstype") or "") == "swap" for node in nodes
        ):
            reject("system")
            continue

        removable = _flag(top.get("rm"))
        hotplug = _flag(top.get("hotplug"))
        transport = _text(top.get("tran"))
        sd_card = sd_probe(name)
        is_loop = top_type == "loop"
        external = removable or hotplug or transport == "usb" or sd_card or is_loop
        if not external:
            reject("internal")
            continue

        rotational = _opt_flag(top.get("rota"))
        vendor, model, serial = _text(top.get("vendor")), _text(top.get("model")), _text(top.get("serial"))
        for node in nodes:
            fstype = _text(node.get("fstype"))
            node_path = str(node.get("path") or f"/dev/{node.get('name')}")
            if not fstype:
                continue
            if fstype in _ENCRYPTED:
                inventory.excluded.append(Excluded(node_path, "encrypted"))
                inventory.encrypted.append(_build(node, top, name, rotational, transport, removable, hotplug, vendor, model, serial, sd_card, mountinfo, is_loop))
                continue
            allowed = LOOP_ALLOWED_FILESYSTEMS if is_loop else DATA_FILESYSTEMS
            if fstype in _NEVER_LISTED or fstype not in allowed or (is_loop and not include_images):
                inventory.excluded.append(Excluded(node_path, "unusable_fs"))
                continue
            mounts = _mountpoints(node)
            if any(overlaps_protected(m, protected) for m in mounts):
                inventory.excluded.append(Excluded(node_path, "bobine_data"))
                continue
            inventory.volumes.append(
                _build(node, top, name, rotational, transport, removable, hotplug, vendor, model, serial, sd_card, mountinfo, is_loop)
            )
    inventory.volumes = dedupe_keys(sorted(inventory.volumes, key=lambda v: (v.disk or "", v.name)))
    return inventory


def dedupe_keys(volumes: list[Volume]) -> list[Volume]:
    """Deux supports portant le même UUID (clones) ne doivent jamais partager une clé : chacun reçoit un suffixe (leur
    enregistrement est de toute façon refusé, voir `duplicate_uuids`)."""
    counts: dict[str, int] = {}
    for v in volumes:
        counts[v.key] = counts.get(v.key, 0) + 1
    return [dataclasses.replace(v, key=f"{v.key}-{v.name}") if counts[v.key] > 1 else v for v in volumes]


def _build(node, top, disk_name, rotational, transport, removable, hotplug, vendor, model, serial, sd_card, mountinfo, is_loop) -> Volume:
    mounts = tuple(_mountpoints(node))
    size = _int(node.get("size"))
    partn = _text(node.get("partn"))
    fs_uuid = _text(node.get("uuid"))
    dev_type = str(node.get("type") or "part")
    kind = classify_kind(transport=transport, rotational=rotational, sd_card=sd_card, name=disk_name, size=_int(top.get("size")) or size, dev_type="loop" if is_loop else dev_type)
    return Volume(
        key=make_key(fs_uuid, serial, model, partn or str(node.get("name")), size),
        device=str(node.get("path") or f"/dev/{node.get('name')}"),
        name=str(node.get("name") or ""),
        fs_uuid=fs_uuid,
        label=_text(node.get("label")),
        fstype=_text(node.get("fstype")),
        size_bytes=size,
        mountpoint=mounts[0] if mounts else None,
        mounts=mounts,
        mount_options=_mount_options(mountinfo, mounts[0] if mounts else None),
        read_only_device=_flag(node.get("ro")),
        removable=removable,
        hotplug=hotplug,
        transport=transport,
        vendor=vendor,
        model=model,
        serial=serial,
        rotational=rotational,
        kind=kind,
        dev_type="loop" if is_loop else dev_type,
        discard_supported=_int(node.get("disc-gran")) > 0,
        disk=disk_name or None,
        sd_card=sd_card,
    )


def duplicate_uuids(volumes: Iterable[Volume]) -> set[str]:
    """UUID portés par plusieurs volumes branchés à la fois (supports clonés) : jamais enregistrables."""
    seen: dict[str, int] = {}
    for v in volumes:
        if v.fs_uuid:
            seen[v.fs_uuid.lower()] = seen.get(v.fs_uuid.lower(), 0) + 1
    return {u for u, n in seen.items() if n > 1}

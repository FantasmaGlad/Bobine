"""Cascade de vérifications PURES avant toute écriture (aucune entrée/sortie : le contexte est fourni par le service)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.storage.lsblk import is_system_mount, overlaps_protected
from .model import DiskInfo
from .options import MIN_SIZE

STACK_FILESYSTEMS = frozenset({
    "crypto_LUKS", "linux_raid_member", "LVM2_member", "zfs_member", "bcache", "ceph_bluestore", "isw_raid_member", "ddf_raid_member",
})
SWAP_FILESYSTEMS = frozenset({"swap", "swsuspend"})

CASCADE = (
    "platform", "present", "allowed", "not_system", "removable", "not_bobine_data", "not_registered", "not_in_use",
    "single_operation", "writable", "not_stacked", "size",
)


@dataclass(frozen=True)
class Check:
    id: str
    ok: bool
    code: str | None = None
    actions: tuple[dict[str, Any], ...] = ()


@dataclass
class GuardContext:
    """Tout ce que la cascade doit savoir, déjà collecté (jamais de chemin donné par le client)."""

    supported: bool = True
    disk: DiskInfo | None = None
    protected_paths: Iterable[str] = ()
    protected_devs: frozenset[int] = frozenset()
    mount_devs: dict[str, int] = field(default_factory=dict)
    registered_uuids: frozenset[str] = frozenset()
    in_use: bool = False
    other_format_active: bool = False
    allow_images: bool = False
    allowlist: frozenset[str] | None = None


def is_external(disk: DiskInfo) -> bool:
    """Amovible au sens strict : drapeau RM, bus USB ou carte SD."""
    return disk.removable or disk.transport == "usb" or disk.sd_card


def candidates(disks: Iterable[DiskInfo], *, allow_images: bool = False) -> list[DiskInfo]:
    """Supports que l'assistant pourrait proposer (sert à l'empreinte de l'inventaire)."""
    out = []
    for d in disks:
        if d.dev_type == "loop":
            if allow_images and any(p.fstype and p.fstype != "squashfs" for p in d.partitions):
                out.append(d)
        elif is_external(d):
            out.append(d)
    return out


def _check(cid: str, ok: bool, code: str | None = None, actions: tuple[dict[str, Any], ...] = ()) -> Check:
    return Check(cid, ok, None if ok else code, actions if not ok else ())


def evaluate(ctx: GuardContext) -> list[Check]:
    """Toutes les vérifications, dans l'ordre de la cascade."""
    checks: list[Check] = []
    disk = ctx.disk
    checks.append(_check("platform", ctx.supported, "format_unsupported_platform"))
    checks.append(_check("present", disk is not None, "format_not_found"))
    if disk is None:
        return checks

    checks.append(_check("allowed", ctx.allowlist is None or disk.path in ctx.allowlist, "format_not_allowed"))

    system = False
    for part in disk.partitions:
        if (part.fstype or "") in SWAP_FILESYSTEMS or any(is_system_mount(m) or m.startswith("[SWAP") for m in part.mountpoints):
            system = True
    checks.append(_check("not_system", not system, "format_system_disk"))

    if disk.dev_type == "loop":
        removable_ok, removable_code = ctx.allow_images, "format_image_not_allowed"
    else:
        removable_ok, removable_code = is_external(disk), "format_internal_disk" if (disk.hotplug or disk.transport in ("sata", "nvme", "ata", "sas")) else "format_not_removable"
    checks.append(_check("removable", removable_ok, removable_code))

    mounts = list(disk.mountpoints)
    data = any(overlaps_protected(m, ctx.protected_paths) for m in mounts) or any(ctx.mount_devs.get(m) in ctx.protected_devs for m in mounts if ctx.mount_devs.get(m) is not None)
    checks.append(_check("not_bobine_data", not data, "format_bobine_data"))

    registered = [p for p in disk.partitions if p.uuid and p.uuid.lower() in ctx.registered_uuids]
    actions = tuple({"id": "unregister", "uuid_known": True} for _ in registered[:1])
    checks.append(_check("not_registered", not registered, "format_library_registered", actions))

    checks.append(_check("not_in_use", not ctx.in_use, "format_in_use"))

    checks.append(_check("single_operation", not ctx.other_format_active, "format_busy_operation"))

    read_only = disk.read_only or any(p.read_only for p in disk.partitions)
    checks.append(_check("writable", not read_only, "format_read_only"))

    stacked = any((p.fstype or "") in STACK_FILESYSTEMS for p in disk.partitions)
    checks.append(_check("not_stacked", not stacked, "format_encrypted_stack"))

    checks.append(_check("size", disk.size_bytes >= MIN_SIZE, "format_too_small"))
    return checks


def first_refusal(checks: Iterable[Check]) -> Check | None:
    for check in checks:
        if not check.ok:
            return check
    return None

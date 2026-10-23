"""Cascade de vérifications PURES avant toute écriture (aucune entrée/sortie : le contexte est fourni par le service).

Chaque vérification a un identifiant, un résultat et, en cas de refus, un code de `refusals.py`. L'ordre est celui
de la cascade : la première vérification refusée fait foi. La même cascade est rejouée sur un inventaire FRAIS au
dernier instant avant d'écrire (le plan peut dater de deux minutes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from app.storage.lsblk import is_system_mount, overlaps_protected
from .model import DiskInfo
from .options import MIN_SIZE

# Systèmes de fichiers qui indiquent un chiffrement ou un ensemble de disques : jamais formatés par Bobine.
STACK_FILESYSTEMS = frozenset({
    "crypto_LUKS", "linux_raid_member", "LVM2_member", "zfs_member", "bcache", "ceph_bluestore", "isw_raid_member", "ddf_raid_member",
})
SWAP_FILESYSTEMS = frozenset({"swap", "swsuspend"})

# Ordre d'exécution de la cascade (et des puces affichées dans le plan).
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

    supported: bool = True                         # le pilote sait formater
    disk: DiskInfo | None = None                   # relu dans l'inventaire courant ; None = introuvable
    protected_paths: Iterable[str] = ()            # dossiers de données de Bobine (réels)
    protected_devs: frozenset[int] = frozenset()   # numéros de périphérique des dossiers de données
    mount_devs: dict[str, int] = field(default_factory=dict)  # point de montage -> st_dev
    registered_uuids: frozenset[str] = frozenset() # UUID (minuscules) des bibliothèques externes enregistrées
    in_use: bool = False                           # import/export/indexation, retrait en cours ou écriture temporaire
    other_format_active: bool = False
    allow_images: bool = False
    allowlist: frozenset[str] | None = None        # environnement d'essai : seuls ces périphériques (/dev/...) sont formatables


def is_external(disk: DiskInfo) -> bool:
    """Amovible au sens strict : drapeau RM, bus USB ou carte SD. Le seul drapeau `HOTPLUG` ne suffit PAS (certains
    contrôleurs SATA internes le portent)."""
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
    """Toutes les vérifications, dans l'ordre de la cascade. Les suivantes d'un refus sont tout de même évaluées
    lorsqu'elles ont un sens (le plan les affiche), mais seule la première refusée est opposée à l'utilisateur."""
    checks: list[Check] = []
    disk = ctx.disk
    checks.append(_check("platform", ctx.supported, "format_unsupported_platform"))
    checks.append(_check("present", disk is not None, "format_not_found"))
    if disk is None:
        return checks

    # 2b. environnement d'essai : liste blanche de périphériques (variable BOBINE_STORAGE_FORMAT_ONLY) ; absente en production
    checks.append(_check("allowed", ctx.allowlist is None or disk.path in ctx.allowlist, "format_not_allowed"))

    # 3. jamais un disque système : montage système, swap, ou partition de démarrage
    system = False
    for part in disk.partitions:
        if (part.fstype or "") in SWAP_FILESYSTEMS or any(is_system_mount(m) or m.startswith("[SWAP") for m in part.mountpoints):
            system = True
    checks.append(_check("not_system", not system, "format_system_disk"))

    # 4. amovible uniquement : USB, carte SD, disque USB (image disque : seulement si explicitement autorisé)
    if disk.dev_type == "loop":
        removable_ok, removable_code = ctx.allow_images, "format_image_not_allowed"
    else:
        removable_ok, removable_code = is_external(disk), "format_internal_disk" if (disk.hotplug or disk.transport in ("sata", "nvme", "ata", "sas")) else "format_not_removable"
    checks.append(_check("removable", removable_ok, removable_code))

    # 5. jamais les dossiers de données de Bobine (chemin contenu ou contenant, ou même périphérique)
    mounts = list(disk.mountpoints)
    data = any(overlaps_protected(m, ctx.protected_paths) for m in mounts) or any(ctx.mount_devs.get(m) in ctx.protected_devs for m in mounts if ctx.mount_devs.get(m) is not None)
    checks.append(_check("not_bobine_data", not data, "format_bobine_data"))

    # 6. jamais un support enregistré comme bibliothèque externe (il faut d'abord le désenregistrer : action proposée)
    registered = [p for p in disk.partitions if p.uuid and p.uuid.lower() in ctx.registered_uuids]
    actions = tuple({"id": "unregister", "uuid_known": True} for _ in registered[:1])
    checks.append(_check("not_registered", not registered, "format_library_registered", actions))

    # 7. ni import/export/indexation/lecture en cours
    checks.append(_check("not_in_use", not ctx.in_use, "format_in_use"))

    # 8. une seule opération destructive à la fois
    checks.append(_check("single_operation", not ctx.other_format_active, "format_busy_operation"))

    # 9. support non protégé en écriture
    read_only = disk.read_only or any(p.read_only for p in disk.partitions)
    checks.append(_check("writable", not read_only, "format_read_only"))

    # 10. ni chiffré, ni RAID/LVM
    stacked = any((p.fstype or "") in STACK_FILESYSTEMS for p in disk.partitions)
    checks.append(_check("not_stacked", not stacked, "format_encrypted_stack"))

    # 11. taille minimale
    checks.append(_check("size", disk.size_bytes >= MIN_SIZE, "format_too_small"))
    return checks


def first_refusal(checks: Iterable[Check]) -> Check | None:
    for check in checks:
        if not check.ok:
            return check
    return None

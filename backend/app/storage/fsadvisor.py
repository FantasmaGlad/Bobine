"""Conseiller de système de fichiers (logique PURE, textes d'interface côté frontend en FR/EN)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OSES = ("linux", "windows", "macos", "android")
MEDIA = ("flash", "ssd", "hdd")

_FS: dict[str, dict[str, Any]] = {
    "ext4": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"linux"}, "readable_elsewhere": set()},
    "ext3": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"linux"}, "readable_elsewhere": set()},
    "ext2": {"journal": False, "permissions": True, "max_file_gib": None, "native": {"linux"}, "readable_elsewhere": set()},
    "btrfs": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"linux"}, "readable_elsewhere": set()},
    "xfs": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"linux"}, "readable_elsewhere": set()},
    "f2fs": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"linux", "android"}, "readable_elsewhere": set()},
    "ntfs": {"journal": True, "permissions": False, "max_file_gib": None, "native": {"windows"}, "readable_elsewhere": {"linux", "macos"}},
    "exfat": {"journal": False, "permissions": False, "max_file_gib": None, "native": {"windows", "macos", "linux", "android"}, "readable_elsewhere": set()},
    "vfat": {"journal": False, "permissions": False, "max_file_gib": 4, "native": {"windows", "macos", "linux", "android"}, "readable_elsewhere": set()},
    "apfs": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"macos"}, "readable_elsewhere": set()},
    "hfsplus": {"journal": True, "permissions": True, "max_file_gib": None, "native": {"macos"}, "readable_elsewhere": {"linux"}},
}
_ALIASES = {"fat": "vfat", "fat16": "vfat", "fat32": "vfat", "msdos": "vfat", "ntfs3": "ntfs", "hfs": "hfsplus"}

RECOMMENDED, ACCEPTABLE, DISCOURAGED = "recommended", "acceptable", "discouraged"


def normalize_fs(fstype: str | None) -> str:
    key = (fstype or "").lower()
    return _ALIASES.get(key, key)


@dataclass(frozen=True)
class Assessment:
    fstype: str
    verdict: str
    reason: str
    notes: tuple[str, ...]
    journal: bool | None
    permissions: bool | None
    max_file_gib: int | None
    write_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "fstype": self.fstype,
            "verdict": self.verdict,
            "reason": self.reason,
            "notes": list(self.notes),
            "journal": self.journal,
            "permissions": self.permissions,
            "max_file_gib": self.max_file_gib,
            "write_allowed": self.write_allowed,
        }


def _base_notes(info: dict, media: str) -> list[str]:
    notes = [
        "journal_unplug_ok" if info["journal"] else "no_journal_unplug_risk",
        "unix_permissions" if info["permissions"] else "no_unix_permissions",
        "file_limit_4gib" if info["max_file_gib"] else "no_file_limit",
    ]
    if media == "flash":
        notes.append("flash_write_wear")
    return notes


def _native_verdict(info: dict, host_os: str, others: tuple[str, ...], notes: list[str]) -> tuple[str, str, bool]:
    if host_os in info["native"]:
        if others and not (set(others) & (info["native"] | info["readable_elsewhere"])):
            notes.append("not_readable_elsewhere")
            return ACCEPTABLE, "not_readable_elsewhere", True
        return RECOMMENDED, "native_host", True
    if host_os in info["readable_elsewhere"]:
        return ACCEPTABLE, "readable_with_driver", True
    return DISCOURAGED, "not_supported_on_host", False


def _verdict(fs: str, info: dict, host_os: str, others: tuple[str, ...], dirty: bool, use: str, notes: list[str]) -> tuple[str, str, bool]:
    if dirty:
        notes.append("dirty_repair_first")
        return DISCOURAGED, "dirty", False
    if fs == "vfat":
        return (DISCOURAGED if use == "library" else ACCEPTABLE), "fat_limits", True
    if fs == "exfat":
        notes.append("prefer_read_only")
        return (RECOMMENDED, "exfat_travel", True) if (others or host_os != "linux") else (ACCEPTABLE, "exfat_no_journal", True)
    if fs == "ntfs":
        if host_os == "windows":
            return RECOMMENDED, "native_host", True
        notes.append("ntfs_unclean_risk")
        return ACCEPTABLE, "ntfs_driver", True
    return _native_verdict(info, host_os, others, notes)


def assess_filesystem(
    fstype: str | None,
    *,
    host_os: str = "linux",
    other_oses: tuple[str, ...] = (),
    media: str = "flash",
    dirty: bool = False,
    use: str = "library",
) -> Assessment:
    """Évalue le système de fichiers d'un volume branché pour l'usage prévu (`library` = lecture directe, `transfer` = import/export)."""
    fs = normalize_fs(fstype)
    info = _FS.get(fs)
    others = tuple(o for o in other_oses if o in OSES and o != host_os)
    if info is None:
        return Assessment(fs or "unknown", "unknown", "unknown_fs", ("unknown_fs_behavior",), None, None, None, False)

    notes = _base_notes(info, media)
    verdict, reason, write_allowed = _verdict(fs, info, host_os, others, dirty, use, notes)
    return Assessment(fs, verdict, reason, tuple(notes), info["journal"], info["permissions"], info["max_file_gib"], write_allowed)


_PROCEDURES: dict[tuple[str, str], list[str]] = {
    ("linux", "ext4"): ["sudo mkfs.ext4 -L BOBINE /dev/sdX1", "GNOME Disques / KDE Partition Manager : Formater > Ext4"],
    ("linux", "exfat"): ["sudo mkfs.exfat -L BOBINE /dev/sdX1", "GNOME Disques : Formater > Autres > exFAT"],
    ("linux", "vfat"): ["sudo mkfs.vfat -F 32 -n BOBINE /dev/sdX1"],
    ("windows", "ntfs"): ["Explorateur de fichiers > clic droit sur le lecteur > Formater > NTFS", "format E: /FS:NTFS /Q"],
    ("windows", "exfat"): ["Explorateur de fichiers > clic droit sur le lecteur > Formater > exFAT", "format E: /FS:exFAT /Q"],
    ("windows", "vfat"): ["Gestion des disques > Formater > FAT32 (au-delà de 32 Go : outil tiers)"],
    ("macos", "apfs"): ["diskutil eraseDisk APFS BOBINE /dev/diskN", "Utilitaire de disque > Effacer > APFS"],
    ("macos", "hfsplus"): ["diskutil eraseDisk JHFS+ BOBINE /dev/diskN", "Utilitaire de disque > Effacer > Mac OS étendu (journalisé)"],
    ("macos", "exfat"): ["diskutil eraseDisk ExFAT BOBINE /dev/diskN", "Utilitaire de disque > Effacer > ExFAT"],
    ("macos", "vfat"): ["diskutil eraseDisk FAT32 BOBINE MBR /dev/diskN"],
    ("android", "exfat"): ["Réglages > Stockage > support USB > Formater (exFAT si proposé)"],
    ("android", "vfat"): ["Réglages > Stockage > support USB > Formater (FAT32)"],
}


def _format_choice(host: str, others: tuple[str, ...], media: str, legacy_readers: bool) -> tuple[str, str, list[str]]:
    if legacy_readers:
        return "vfat", "legacy_fat32", ["file_limit_4gib", "no_journal_unplug_risk"]
    if host == "android":
        return "exfat", "android_host", ["android_ext4_unmounted", "no_journal_unplug_risk"]
    if others:
        return "exfat", "travels_between_os", ["no_file_limit", "no_journal_unplug_risk", "prefer_read_only", "clean_unmount_required"]
    if host == "linux":
        return "ext4", "linux_only", ["journal_unplug_ok", "unix_permissions", "no_file_limit"]
    if host == "windows":
        return "ntfs", "windows_only", ["journal_unplug_ok", "no_file_limit"]
    if media == "hdd":
        return "hfsplus", "macos_only_hdd", ["journal_unplug_ok", "no_file_limit"]
    return "apfs", "macos_only_ssd", ["journal_unplug_ok", "no_file_limit"]


def recommend_format(
    host_os: str,
    other_oses: tuple[str, ...] = (),
    media: str = "flash",
    *,
    use: str = "library",
    legacy_readers: bool = False,
) -> dict[str, Any]:
    """Système de fichiers conseillé selon l'OS hôte de Bobine et les autres OS qui brancheront le support."""
    host = host_os if host_os in OSES else "linux"
    others = tuple(sorted({o for o in other_oses if o in OSES and o != host}))
    fs, reason, notes = _format_choice(host, others, media, legacy_readers)
    if media == "flash":
        notes.append("flash_write_wear")

    alternatives = []
    if fs != "exfat" and host != "android":
        alternatives.append({"fstype": "exfat", "reason": "travels_between_os"})
    if fs != "vfat":
        alternatives.append({"fstype": "vfat", "reason": "legacy_fat32"})
    return {
        "fstype": fs,
        "reason": reason,
        "notes": notes,
        "host_os": host,
        "other_oses": list(others),
        "media": media if media in MEDIA else "flash",
        "procedures": {os_name: _PROCEDURES.get((os_name, fs), []) for os_name in OSES if _PROCEDURES.get((os_name, fs))},
        "alternatives": alternatives,
        "destructive": True,
    }

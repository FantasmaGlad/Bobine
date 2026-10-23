"""Conseiller de système de fichiers (logique PURE, textes d'interface côté frontend en FR/EN).

Deux usages :

* `assess_filesystem` : pour un volume DÉJÀ branché, verdict (recommandé / acceptable / déconseillé),
  raison et conséquences sur la longévité (journal, droits, limite de taille, sûreté à l'arrachage) ;
* `recommend_format` : selon l'OS qui héberge Bobine ET les autres OS qui brancheront le support,
  système de fichiers conseillé, avec la procédure INDICATIVE par OS.

Ce module ne formate JAMAIS : il décrit, il n'exécute rien. Un éventuel assistant de formatage est une
action destructive hors de la phase 1 (décision du mainteneur).

Les raisons sont des CODES stables (`reason`, `notes`) ; le frontend les traduit (`storage.fs.*`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OSES = ("linux", "windows", "macos", "android")
# Support : flash (clé, SD, SSD) ou rotatif.
MEDIA = ("flash", "ssd", "hdd")

# Propriétés par système de fichiers : journal (survit mieux à un arrachage), droits Unix, limite de taille d'un fichier,
# systèmes qui le lisent/écrivent sans composant tiers.
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
    verdict: str  # recommended | acceptable | discouraged | unknown
    reason: str  # code
    notes: tuple[str, ...]  # codes de conséquences (longévité, droits, limite, arrachage)
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

    notes: list[str] = []
    if not info["journal"]:
        notes.append("no_journal_unplug_risk")
    else:
        notes.append("journal_unplug_ok")
    if info["permissions"]:
        notes.append("unix_permissions")
    else:
        notes.append("no_unix_permissions")
    if info["max_file_gib"]:
        notes.append("file_limit_4gib")
    else:
        notes.append("no_file_limit")
    if media == "flash":
        notes.append("flash_write_wear")

    write_allowed = True
    verdict, reason = ACCEPTABLE, "works"

    if dirty:
        verdict, reason = DISCOURAGED, "dirty"
        write_allowed = False
        notes.append("dirty_repair_first")
    elif fs == "vfat":
        verdict, reason = (DISCOURAGED, "fat_limits") if use == "library" else (ACCEPTABLE, "fat_limits")
    elif fs == "exfat":
        # Le meilleur compromis pour un support qui voyage, mais sans journal : lecture seule privilégiée.
        verdict, reason = (RECOMMENDED, "exfat_travel") if (others or host_os != "linux") else (ACCEPTABLE, "exfat_no_journal")
        notes.append("prefer_read_only")
    elif fs == "ntfs":
        if host_os == "windows":
            verdict, reason = RECOMMENDED, "native_host"
        else:
            verdict, reason = ACCEPTABLE, "ntfs_driver"
            notes.append("ntfs_unclean_risk")
    elif host_os in info["native"]:
        verdict, reason = RECOMMENDED, "native_host"
        if others and not (set(others) & (info["native"] | info["readable_elsewhere"])):
            verdict, reason = ACCEPTABLE, "not_readable_elsewhere"
            notes.append("not_readable_elsewhere")
    elif host_os in info["readable_elsewhere"]:
        verdict, reason = ACCEPTABLE, "readable_with_driver"
    else:
        verdict, reason = DISCOURAGED, "not_supported_on_host"
        write_allowed = False
    return Assessment(fs, verdict, reason, tuple(notes), info["journal"], info["permissions"], info["max_file_gib"], write_allowed)


# Procédures INDICATIVES (jamais exécutées par Bobine). `{device}` est un exemple à remplacer.
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


def recommend_format(
    host_os: str,
    other_oses: tuple[str, ...] = (),
    media: str = "flash",
    *,
    use: str = "library",
    legacy_readers: bool = False,
) -> dict[str, Any]:
    """Système de fichiers conseillé selon l'OS hôte de Bobine et les autres OS qui brancheront le support.

    `legacy_readers` : très vieux lecteurs (autoradio, TV ancienne) qui ne lisent que FAT32."""
    host = host_os if host_os in OSES else "linux"
    others = tuple(sorted({o for o in other_oses if o in OSES and o != host}))
    notes: list[str] = []

    if legacy_readers:
        fs, reason = "vfat", "legacy_fat32"
        notes += ["file_limit_4gib", "no_journal_unplug_risk"]
    elif host == "android":
        fs, reason = "exfat", "android_host"
        notes += ["android_ext4_unmounted", "no_journal_unplug_risk"]
    elif others:
        fs, reason = "exfat", "travels_between_os"
        notes += ["no_file_limit", "no_journal_unplug_risk", "prefer_read_only", "clean_unmount_required"]
    elif host == "linux":
        fs, reason = "ext4", "linux_only"
        notes += ["journal_unplug_ok", "unix_permissions", "no_file_limit"]
    elif host == "windows":
        fs, reason = "ntfs", "windows_only"
        notes += ["journal_unplug_ok", "no_file_limit"]
    else:  # macOS seul
        if media == "hdd":
            fs, reason = "hfsplus", "macos_only_hdd"
        else:
            fs, reason = "apfs", "macos_only_ssd"
        notes += ["journal_unplug_ok", "no_file_limit"]
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
        "destructive": True,  # formater efface tout : Bobine ne le fait jamais seul
    }

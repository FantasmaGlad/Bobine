"""Systèmes de fichiers proposés, étiquettes, paramètres de formatage adaptés à la capacité (logique PURE).

Un seul mode de formatage : RAPIDE (aucun écrasement complet du support, pour ménager les mémoires flash).
Les raisons et conséquences sont des CODES stables que l'interface traduit (`storage.format.*`)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.storage import fsadvisor
from .model import DiskInfo, serial_tail

GIB = 1024 ** 3
MIB = 1024 ** 2
TIB = 1024 ** 4
ALIGNMENT = MIB                       # première partition à 1 Mio
MIN_SIZE = 64 * MIB                   # en dessous, un système de fichiers de données n'a pas de sens

LINUX_FS_GUID = "0fc63daf-8483-4772-8e79-3d69d8477de4"
BASIC_DATA_GUID = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"   # exFAT, NTFS, FAT32 : lu par Windows et macOS

# Ordre d'affichage : le conseiller peut en recommander un, l'utilisateur choisit.
SUPPORTED = ("ext4", "exfat", "vfat", "ntfs")


@dataclass(frozen=True)
class FsSpec:
    fs: str                      # nom de l'interface (ext4, exfat, vfat, ntfs)
    udisks_type: str             # type passé à udisks2 (`Block.Format`)
    tools: tuple[str, ...]       # l'un de ces programmes doit exister (mkfs.*)
    label_max: int
    partition_guid: str
    take_ownership: bool         # le compte de Bobine doit pouvoir écrire à la racine (droits Unix)
    package: str                 # paquet Debian qui fournit l'outil


SPECS: dict[str, FsSpec] = {
    "ext4": FsSpec("ext4", "ext4", ("mkfs.ext4",), 16, LINUX_FS_GUID, True, "e2fsprogs"),
    "exfat": FsSpec("exfat", "exfat", ("mkfs.exfat",), 11, BASIC_DATA_GUID, False, "exfatprogs"),
    "vfat": FsSpec("vfat", "vfat", ("mkfs.vfat", "mkfs.fat"), 11, BASIC_DATA_GUID, False, "dosfstools"),
    "ntfs": FsSpec("ntfs", "ntfs", ("mkntfs", "mkfs.ntfs"), 32, BASIC_DATA_GUID, False, "ntfs-3g"),
}

# Conséquences propres à chaque système de fichiers, en plus de celles du conseiller (`fsadvisor`).
_FS_NOTES = {
    "ext4": ("journal_unplug_ok", "unix_permissions", "no_file_limit", "linux_only_reader"),
    "exfat": ("no_journal_unplug_risk", "prefer_read_only", "clean_unmount_required", "no_file_limit", "reads_everywhere"),
    "vfat": ("no_journal_unplug_risk", "file_limit_4gib", "reads_everywhere"),
    "ntfs": ("journal_unplug_ok", "no_file_limit", "windows_native"),
}

_FORBIDDEN_COMMON = re.compile(r"[\x00-\x1f\x7f/\\\"]")
_FORBIDDEN_FAT = re.compile(r"[*?.,;:/\\|+=<>\[\]\"]")


class LabelError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_label(fs: str, raw: str | None) -> str:
    """Étiquette valide pour ce système de fichiers (sinon `LabelError`) ; FAT32 est converti en majuscules."""
    spec = SPECS.get(fs)
    if spec is None:
        raise LabelError("fs_unknown")
    text = unicodedata.normalize("NFC", (raw or "").strip())
    if not text:
        raise LabelError("label_empty")
    if _FORBIDDEN_COMMON.search(text):
        raise LabelError("label_chars")
    if fs == "vfat":
        text = text.upper()
        if _FORBIDDEN_FAT.search(text):
            raise LabelError("label_chars")
        if not text.isascii():
            raise LabelError("label_chars")
    size = len(text.encode("utf-8")) if fs == "ext4" else len(text)
    if size > spec.label_max:
        raise LabelError("label_too_long")
    return text


def suggested_label(disk: DiskInfo, fs: str) -> str:
    """Étiquette proposée : l'actuelle si elle est valable pour ce système de fichiers, sinon `BOBINE`."""
    for part in disk.partitions:
        if part.label:
            try:
                return normalize_label(fs, part.label)
            except LabelError:
                break
    return "BOBINE"


def exfat_cluster_bytes(size_bytes: int) -> int:
    """Taille de cluster exFAT selon la capacité (défauts de Microsoft) : 4 Kio jusqu'à 256 Mio, 32 Kio jusqu'à 32 Gio, 128 Kio au-delà."""
    if size_bytes <= 256 * MIB:
        return 4096
    if size_bytes <= 32 * GIB:
        return 32768
    return 131072


def mkfs_args(fs: str, partition_bytes: int) -> list[str]:
    """Arguments passés à l'outil de formatage (via udisks2 `mkfs-args`). Aucun n'écrase le support en entier.

    * ext4 : aucun bloc réservé au superutilisateur (`-m 0`), disque de DONNÉES : tout l'espace sert aux médias ; peu d'inodes
      pour les grands volumes de gros fichiers (`-T largefile`) ;
    * exFAT : cluster adapté à la capacité ;
    * FAT32 : FAT32 forcée ;
    * NTFS : formatage rapide (udisks2 le fait déjà ; `-Q` le rend explicite)."""
    if fs == "ext4":
        args = ["-m", "0"]
        if partition_bytes >= 8 * GIB:
            args += ["-T", "largefile"]
        return args
    if fs == "exfat":
        return ["-c", str(exfat_cluster_bytes(partition_bytes))]
    if fs == "vfat":
        return ["-F", "32"]
    if fs == "ntfs":
        return ["-Q"]
    raise LabelError("fs_unknown")


def partition_bytes_for(disk_bytes: int) -> int:
    """Taille utile de la partition créée : tout le disque moins l'alignement de tête et la table GPT de fin (~1 Mio)."""
    return max(0, disk_bytes - 2 * ALIGNMENT)


def capacity_limit(fs: str, disk_bytes: int) -> str | None:
    """Code de la limite de capacité qui empêche ce système de fichiers, sinon None."""
    if fs == "vfat" and disk_bytes > 2 * TIB:
        return "fat32_over_2tib"
    return None


def confirm_expected(disk: DiskInfo) -> dict[str, str]:
    """Texte à saisir pour confirmer : le nom du support ; à défaut, les 4 derniers caractères de son numéro de série ;
    à défaut, son modèle ; en dernier recours le mot ERASE."""
    for part in disk.partitions:
        if part.label:
            return {"mode": "name", "expected": part.label}
    tail = serial_tail(disk)
    if tail:
        return {"mode": "serial_tail", "expected": tail}
    model = " ".join(p for p in (disk.vendor, disk.model) if p)
    if model:
        return {"mode": "model", "expected": model}
    return {"mode": "word", "expected": "ERASE"}


def confirm_matches(disk: DiskInfo, typed: str | None) -> bool:
    expected = confirm_expected(disk)["expected"]
    a = unicodedata.normalize("NFC", (typed or "").strip()).casefold()
    b = unicodedata.normalize("NFC", expected.strip()).casefold()
    return bool(a) and a == b


def option_for(fs: str, disk: DiskInfo, *, tool_present: bool, others: tuple[str, ...], media: str) -> dict[str, Any]:
    """Une ligne du plan par système de fichiers : disponible ?, verdict du conseiller, conséquences, étiquette proposée."""
    spec = SPECS[fs]
    verdict = fsadvisor.assess_filesystem(fs, host_os="linux", other_oses=others, media=media, use="library")
    limit = capacity_limit(fs, disk.size_bytes)
    reasons = []
    if not tool_present:
        reasons.append(("tool_missing", f"Outil absent : installez le paquet {spec.package}."))
    if limit:
        reasons.append((limit, "Capacité trop grande pour ce système de fichiers."))
    notes = list(dict.fromkeys(list(_FS_NOTES.get(fs, ())) + list(verdict.notes)))
    if media == "flash":
        notes.append("quick_format_only")
    return {
        "fs": fs,
        "available": not reasons,
        "unavailable": reasons[0][0] if reasons else None,
        "install_package": spec.package if not tool_present else None,
        "verdict": verdict.verdict,
        "reason": verdict.reason,
        "notes": list(dict.fromkeys(notes)),
        "max_file_gib": verdict.max_file_gib,
        "label_max": spec.label_max,
        "label": suggested_label(disk, fs),
        "cluster_bytes": exfat_cluster_bytes(partition_bytes_for(disk.size_bytes)) if fs == "exfat" else None,
    }

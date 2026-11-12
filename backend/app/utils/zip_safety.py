"""Extraction sûre d'archives ZIP et tar — un membre nommé `../../etc/x`."""

import logging
import shutil
import tarfile
import zipfile
from pathlib import Path
from app.utils import media_formats

logger = logging.getLogger(__name__)

ARCHIVE_EXTENSIONS = media_formats.ARCHIVE


class UnsafeZipError(Exception):
    """Levée quand une archive contient un membre qui sortirait du dossier de destination."""


class InvalidArchiveError(ValueError):
    """Le fichier n'est ni un ZIP ni un tar lisible."""


MAX_ARCHIVE_MEMBERS = 50_000
MAX_ARCHIVE_FREE_SPACE_RATIO = 0.9


def _label(name: str) -> str:
    text = name if len(name) <= 200 else name[:200] + "…"
    return repr(text)


def _size(value: int) -> str:
    if value >= 1024 ** 3:
        return f"{value / (1024 ** 3):.1f} Gio"
    if value >= 1024 ** 2:
        return f"{value // (1024 ** 2)} Mio"
    return f"{value // 1024} Kio"


def _check_archive_budget(dest_dir: Path, total_bytes: int) -> None:
    probe = dest_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free
    except OSError as exc:
        logger.warning("Espace libre de %s inconnu, budget de l'archive non contrôlé : %s", probe, exc)
        return
    if total_bytes > free * MAX_ARCHIVE_FREE_SPACE_RATIO:
        raise UnsafeZipError(
            f"Archive invalide : {_size(total_bytes)} décompressés pour {_size(free)} libres."
        )


def _inside(dest_dir: Path, name: str) -> bool:
    resolved = (dest_dir / name).resolve()
    return resolved == dest_dir or dest_dir in resolved.parents


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """Équivalent sûr de `zf.extractall(dest_dir)`."""
    dest_dir = dest_dir.resolve()
    members = zf.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise UnsafeZipError(f"Archive ZIP invalide : plus de {MAX_ARCHIVE_MEMBERS} membres.")
    total = 0
    for member in members:
        if not _inside(dest_dir, member.filename):
            raise UnsafeZipError(
                f"Archive ZIP invalide : le membre {_label(member.filename)} sortirait du dossier de destination."
            )
        if member.file_size < 0:
            raise UnsafeZipError(f"Archive ZIP invalide : taille invalide pour {_label(member.filename)}.")
        total += member.file_size
    _check_archive_budget(dest_dir, total)
    zf.extractall(dest_dir)


def safe_extract_tar(tf: tarfile.TarFile, dest_dir: Path) -> None:
    """Extrait un tar après avoir vérifié TOUS ses membres : chemins sous `dest_dir`, fichiers et dossiers seulement."""
    dest_dir = dest_dir.resolve()
    members: list[tarfile.TarInfo] = []
    total = 0
    for member in tf:
        if len(members) >= MAX_ARCHIVE_MEMBERS:
            raise UnsafeZipError(f"Archive invalide : plus de {MAX_ARCHIVE_MEMBERS} membres.")
        if not _inside(dest_dir, member.name):
            raise UnsafeZipError(f"Archive invalide : le membre {_label(member.name)} sortirait du dossier de destination.")
        if not (member.isfile() or member.isdir()):
            raise UnsafeZipError(f"Archive invalide : le membre {_label(member.name)} n'est ni un fichier ni un dossier.")
        if member.size < 0:
            raise UnsafeZipError(f"Archive invalide : taille invalide pour {_label(member.name)}.")
        members.append(member)
        total += member.size
    _check_archive_budget(dest_dir, total)
    for member in members:
        target = dest_dir / member.name
        try:
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = tf.extractfile(member)
            if source is None:
                continue
            with source, open(target, "wb") as out:
                shutil.copyfileobj(source, out, 1024 * 1024)
        except OSError as exc:
            raise InvalidArchiveError(
                f"L'archive est invalide ou n'a pas pu être extraite : membre {_label(member.name)}."
            ) from exc


def safe_extract_archive(path: Path, dest_dir: Path) -> None:
    """Extrait un ZIP ou un tar (non compressé, gzip, xz, bzip2), reconnu à son contenu."""
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path, "r") as zf:
                safe_extract_zip(zf, dest_dir)
        except zipfile.BadZipFile as exc:
            raise InvalidArchiveError("L'archive ZIP est invalide ou corrompue.") from exc
        return
    with open(path, "rb") as probe:
        if probe.read(6) == b"7z\xbc\xaf\x27\x1c":
            raise InvalidArchiveError("Le format 7z n'est pas pris en charge : utiliser une archive ZIP ou tar.")
    try:
        with tarfile.open(path, "r:*") as tf:
            safe_extract_tar(tf, dest_dir)
    except tarfile.TarError as exc:
        raise InvalidArchiveError("L'archive est invalide, corrompue ou d'un format non pris en charge (ZIP ou tar).") from exc

"""Extraction sûre d'archives ZIP et tar — un membre nommé `../../etc/x` (ou équivalent) fait normalement
écrire `ZipFile.extractall()` hors du dossier de destination prévu, sans
qu'aucune vérification native ne s'y oppose. Pour tar, les liens et fichiers spéciaux sont refusés en plus :
le runtime Android (Python 3.11) n'a pas toujours le filtre `data` de `tarfile`."""

import shutil
import tarfile
import zipfile
from pathlib import Path
from app.utils import media_formats

# Extensions acceptées par les formulaires d'import ; le format réel est reconnu au contenu, pas au nom.
ARCHIVE_EXTENSIONS = media_formats.ARCHIVE


class UnsafeZipError(Exception):
    """Levée quand une archive contient un membre qui sortirait du dossier de destination."""


class InvalidArchiveError(ValueError):
    """Le fichier n'est ni un ZIP ni un tar lisible."""


def _inside(dest_dir: Path, name: str) -> bool:
    resolved = (dest_dir / name).resolve()
    return resolved == dest_dir or dest_dir in resolved.parents


def safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path) -> None:
    """
    Équivalent sûr de `zf.extractall(dest_dir)` : vérifie D'ABORD que chaque
    membre de l'archive résout bien sous `dest_dir` avant d'extraire quoi que
    ce soit — une archive malveillante ne doit laisser AUCUN fichier sur
    disque, pas juste s'arrêter au milieu de l'extraction.
    """
    dest_dir = dest_dir.resolve()
    for member in zf.namelist():
        if not _inside(dest_dir, member):
            raise UnsafeZipError(
                f"Archive ZIP invalide : le membre « {member} » sortirait du dossier de destination."
            )
    zf.extractall(dest_dir)


def safe_extract_tar(tf: tarfile.TarFile, dest_dir: Path) -> None:
    """Extrait un tar après avoir vérifié TOUS ses membres : chemins sous `dest_dir`, fichiers et dossiers seulement."""
    dest_dir = dest_dir.resolve()
    members = tf.getmembers()
    for member in members:
        if not _inside(dest_dir, member.name):
            raise UnsafeZipError(f"Archive invalide : le membre « {member.name} » sortirait du dossier de destination.")
        if not (member.isfile() or member.isdir()):
            raise UnsafeZipError(f"Archive invalide : le membre « {member.name} » n'est ni un fichier ni un dossier.")
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
                f"L'archive est invalide ou n'a pas pu être extraite : membre « {member.name} »."
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
    try:
        with tarfile.open(path, "r:*") as tf:
            safe_extract_tar(tf, dest_dir)
    except tarfile.TarError as exc:
        raise InvalidArchiveError("L'archive est invalide, corrompue ou d'un format non pris en charge (ZIP ou tar).") from exc

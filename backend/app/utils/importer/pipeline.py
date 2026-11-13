"""Chaîne commune d'import d'un média : sonde, normalisation ou déplacement, miniature, enregistrement."""
import logging
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.database import SessionLocal
from app.models import ImportSource
from app.utils.activity_log import log_activity
from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job
from app.utils.importer.metadata import extract_metadata_or_unknown
from app.utils.importer.staging import wait_for_file_to_copy
from app.utils.video_utils.compatibility import check_compatibility
from app.utils.video_utils.normalize import estimate_normalize_seconds, normalize_video
from app.utils.video_utils.thumbnails import generate_placeholder_thumbnail, generate_thumbnail

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Target:
    directory: Callable[[], str]
    prefix: str
    label: str
    strict_codec: bool = False
    placeholder: bool = False


def _remove(path: Any, context: str) -> None:
    if path and Path(path).exists():
        try:
            os.remove(path)
        except Exception as exc:
            logger.debug("%s : %s", context, exc)


def _check_cancelled(job_id: str | None) -> None:
    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé")


def wait_if_watched(src_path: str, original_filename: str, source: ImportSource) -> None:
    if source == ImportSource.watched_folder and not wait_for_file_to_copy(src_path):
        raise TimeoutError(f"Le fichier {original_filename} ne s'est pas stabilisé dans le temps imparti.")


def _reject_drm(src_path: str, original_filename: str) -> None:
    if Path(src_path).exists():
        try:
            os.remove(src_path)
        except Exception as exc:
            logger.error(f"Impossible de supprimer le fichier DRM {src_path}: {exc}")
    raise ValueError(f"Le fichier {original_filename} est protégé par DRM et ne peut pas être lu.")


def _normalize(src_path: str, directory: Path, stem: str, file_id: str, clean_name: str, target: Target,
               compat: dict, meta: dict, original_filename: str, job_id: str | None) -> tuple[Path, dict]:
    update_job(job_id, stage="normalizing", estimated_seconds=estimate_normalize_seconds(meta))
    staged = directory / f"temp_{file_id}_{clean_name}"
    converted = directory / f"temp_norm_{file_id}_{stem}.mp4"
    final = directory / f"{target.prefix}_{file_id}_{stem}.mp4"
    logger.info(f"Normalisation de {src_path} vers {final} via actions: {compat['actions']}")
    shutil.move(src_path, staged)
    try:
        normalize_video(str(staged), str(converted), compat["actions"], source_metadata=meta, job_id=job_id)
        if converted.exists():
            shutil.move(converted, final)
        return final, extract_metadata_or_unknown(str(final), original_filename)
    finally:
        _remove(staged, "normalisation")
        _remove(converted, "normalisation")


def _place(src_path: str, original_filename: str, target: Target, compat: dict, meta: dict,
           job_id: str | None, placed: list) -> dict:
    file_id = uuid.uuid4().hex
    clean_name = "".join(c for c in original_filename if c.isalnum() or c in (".", "_", "-")).strip()
    directory = Path(target.directory())
    if compat["needs_normalization"]:
        dest, meta = _normalize(src_path, directory, Path(clean_name).stem, file_id, clean_name, target,
                                compat, meta, original_filename, job_id)
        placed.append(dest)
        return meta
    update_job(job_id, stage="copying")
    dest = directory / f"{target.prefix}_{file_id}_{clean_name}"
    logger.info(f"Déplacement direct de {src_path} vers {dest}")
    shutil.move(src_path, dest)
    placed.append(dest)
    return meta


def thumbnail_or_placeholder(make: Callable[[], str], dest: Path, original_filename: str, placeholder: bool,
                             thumbnails_dir: str) -> str | None:
    try:
        return make()
    except Exception as exc:
        logger.error(f"Échec de la génération de miniature pour {dest}: {exc}")
    if not placeholder:
        return None
    try:
        return generate_placeholder_thumbnail(thumbnails_dir, Path(original_filename).stem)
    except Exception as exc:
        logger.error(f"Miniature de secours impossible pour {dest}: {exc}")
        return None


def save(row: Any, event: str, detail: Callable[[Any], str], files: list, label: str, original_filename: str):
    db = SessionLocal()
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(f"{label} indexé avec succès : {row.title} (ID: {row.id})")
        log_activity(db, event, detail(row))
        db.refresh(row)
        return row
    except Exception as exc:
        db.rollback()
        logger.error(f"Erreur DB lors de l'enregistrement de {original_filename}: {exc}")
        for path in files:
            _remove(path, "enregistrement")
        raise
    finally:
        db.close()


def import_media(src_path: str, original_filename: str, source: ImportSource, job_id: str | None, target: Target,
                 thumbnails_dir: str, build: Callable[[Path, dict, str | None], Any], event: str,
                 detail: Callable[[Any], str]):
    update_job(job_id, stage="probing")
    meta = extract_metadata_or_unknown(src_path, original_filename)
    if meta["is_drm"]:
        _reject_drm(src_path, original_filename)
    compat = check_compatibility(meta, src_path, **({"strict_video_codec": True} if target.strict_codec else {}))
    Path(target.directory()).mkdir(parents=True, exist_ok=True)
    Path(thumbnails_dir).mkdir(parents=True, exist_ok=True)
    placed: list = []
    try:
        _check_cancelled(job_id)
        meta = _place(src_path, original_filename, target, compat, meta, job_id, placed)
        dest = placed[0]
        _check_cancelled(job_id)
        update_job(job_id, stage="thumbnail")
        thumb = thumbnail_or_placeholder(
            lambda: generate_thumbnail(str(dest), thumbnails_dir, meta["duration_seconds"]),
            dest, original_filename, target.placeholder, thumbnails_dir)
        placed.append(thumb)
        _check_cancelled(job_id)
        update_job(job_id, stage="saving")
        return save(build(dest, meta, thumb), event, detail, placed, target.label, original_filename)
    except JobCancelledError:
        logger.info(f"Import {job_id} annulé par l'utilisateur : nettoyage des fichiers partiels...")
        for path in placed:
            _remove(path, "annulation")
        raise
    except Exception as exc:
        logger.error(f"Erreur lors de l'importation de {original_filename}: {exc}")
        if source == ImportSource.watched_folder:
            _remove(src_path, "import")
        raise

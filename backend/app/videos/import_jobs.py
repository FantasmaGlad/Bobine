"""Tâches d'import en arrière-plan : une vidéo envoyée (avec ses sous-titres) ou une archive de vidéos."""

from __future__ import annotations

import logging
import os

from app.database import SessionLocal
from app.models import ImportSource, Video
from app.utils.archive_import import import_media_archive
from app.utils.import_jobs import JobCancelledError, update_job
from app.utils.importer.formats import SUPPORTED_EXTENSIONS
from app.utils.importer.video import import_video

from .events import notify_library
from .subtitles import attach_imported_subtitle

logger = logging.getLogger(__name__)


def _apply_fields(db_video: Video, fields: dict[str, str | None]) -> None:
    for name, value in fields.items():
        if value:
            setattr(db_video, name, value)


def _record(video_id: int, fields: dict[str, str | None], subtitle_temps: list[tuple[str, str]]) -> int:
    with SessionLocal() as db:
        db_video = db.query(Video).filter(Video.id == video_id).first()
        if db_video is None:
            return video_id
        _apply_fields(db_video, fields)
        db.commit()
        for temp_path, name in subtitle_temps:
            try:
                attach_imported_subtitle(db, db_video.id, temp_path, name)
            except Exception as exc:
                logger.warning("Erreur import sous-titre joint %s pour video %s : %s", name, db_video.id, exc)
        return db_video.id


def _remove(paths: list[str]) -> None:
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as exc:
                logger.debug("Fichier temporaire d'import non supprimé %s : %s", path, exc)


def run_video_import_job(job_id: str, temp_path: str, filename: str, fields: dict[str, str | None], subtitle_temps: list[tuple[str, str]]) -> None:
    try:
        video = import_video(temp_path, filename, ImportSource.upload, job_id=job_id)
        result_id = _record(video.id, fields, subtitle_temps)
        notify_library("video_imported")
        update_job(job_id, stage="done", result_id=result_id)
    except JobCancelledError:
        logger.info("Tâche d'import vidéo %s annulée.", job_id)
        update_job(job_id, stage="cancelled")
    except Exception as exc:
        logger.error("Erreur lors de l'upload et de l'import de la vidéo (job %s): %s", job_id, exc, exc_info=True)
        update_job(job_id, stage="error", error=str(exc))
    finally:
        _remove([temp_path, *(path for path, _ in subtitle_temps)])


def run_video_archive_job(job_id: str, archive_path: str) -> None:
    try:
        videos = import_media_archive(
            archive_path, job_id, SUPPORTED_EXTENSIONS,
            lambda path, name: import_video(path, name, ImportSource.upload, job_id=job_id), "vidéo",
        )
        notify_library("video_imported")
        update_job(job_id, stage="done", result_id=videos[0].id)
    except JobCancelledError:
        update_job(job_id, stage="cancelled")
    except Exception as exc:
        logger.error("Import d'une archive de vidéos (job %s) échoué : %s", job_id, exc, exc_info=True)
        update_job(job_id, stage="error", error=str(exc))

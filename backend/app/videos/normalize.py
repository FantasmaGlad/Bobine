"""Normalisation d'une vidéo existante en tâche de fond ; l'original est remis en place si elle échoue."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import Video
from app.utils.video_utils.normalize import normalize_video
from app.utils.video_utils.probe import extract_metadata
from app.utils.video_utils.thumbnails import generate_thumbnail

logger = logging.getLogger(__name__)


def _apply_normalized_metadata(video: Video, new_path: Path) -> None:
    meta = extract_metadata(str(new_path))
    video.file_path = str(new_path)
    video.duration_seconds = meta.get("duration_seconds")
    video.width = meta.get("width")
    video.height = meta.get("height")
    video.codec = meta.get("codec")
    for field in ("audio_channels", "audio_codec", "fps", "bitrate_kbps"):
        if meta.get(field) is not None:
            setattr(video, field, meta[field])
    if not video.description and meta.get("description"):
        video.description = meta["description"]
    try:
        video.thumbnail_path = generate_thumbnail(str(new_path), settings.thumbnails_dir, meta["duration_seconds"])
    except Exception as exc:
        logger.error("Miniature post-normalisation échouée : %s", exc)


def _normalize_in_place(db, video: Video, actions: list, source_metadata: dict | None) -> None:
    old_path = Path(video.file_path)
    old_thumbnail = video.thumbnail_path
    file_id = uuid.uuid4().hex
    staged = old_path.parent / f"temp_{file_id}_{old_path.name}"
    new_path = old_path.parent / f"video_{file_id}_{old_path.stem}.mp4"
    shutil.move(old_path, staged)
    try:
        normalize_video(str(staged), str(new_path), actions, source_metadata=source_metadata)
        _apply_normalized_metadata(video, new_path)
        db.commit()
    except Exception:
        db.rollback()
        new_path.unlink(missing_ok=True)
        shutil.move(staged, old_path)
        raise
    staged.unlink(missing_ok=True)
    if old_thumbnail and old_thumbnail != video.thumbnail_path:
        Path(old_thumbnail).unlink(missing_ok=True)


def bg_normalize(video_id: int, actions: list, source_metadata: dict | None = None) -> None:
    try:
        with SessionLocal() as db:
            video = db.query(Video).filter(Video.id == video_id).first()
            if not video:
                return
            _normalize_in_place(db, video, actions, source_metadata)
        logger.info("Vidéo ID %s normalisée en tâche de fond.", video_id)
    except Exception as exc:
        logger.error("Erreur lors de la normalisation en tâche de fond de la vidéo %s : %s", video_id, exc)

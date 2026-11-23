"""Fichiers d'une vidéo : renommage d'après le titre, miniature manuelle, suppression complète."""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ScheduleTargetType, Video
from app.scheduling.targets import drop_schedules_targeting, remove_jobs
from app.utils import chapters as chapter_utils
from app.utils.web_rendition import remove_web_file
from app.videos.storyboard import storyboard_path

logger = logging.getLogger(__name__)

_STORED_NAME = re.compile(r"^video_([a-f0-9]{32})_(.+)$")


def rename_video_file(video: Video, title: str) -> None:
    """Renomme le fichier d'une vidéo d'après son titre ; jamais sur un support externe (le titre change alors en base seulement)."""
    old_path = Path(video.file_path)
    if not old_path.exists() or video.storage_id is not None:
        return
    match = _STORED_NAME.match(old_path.name)
    uuid_str = match.group(1) if match else uuid.uuid4().hex
    clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or "video"
    new_path = old_path.parent / f"video_{uuid_str}_{clean_title}{old_path.suffix}"
    if new_path == old_path:
        return
    try:
        shutil.move(old_path, new_path)
        video.file_path = str(new_path)
        logger.info("Fichier vidéo renommé de %s à %s", old_path.name, new_path.name)
    except Exception as exc:
        logger.error("Erreur lors du renommage du fichier vidéo %s -> %s : %s", old_path, new_path, exc)


def write_manual_thumbnail(source: BinaryIO) -> Path:
    """Image envoyée par l'utilisateur, vérifiée puis réduite en JPEG ; ValueError si ce n'est pas une image."""
    from PIL import Image, UnidentifiedImageError

    try:
        Image.open(source).verify()
        source.seek(0)
        img = Image.open(source).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError(str(exc)) from exc
    thumbnails_dir = Path(settings.thumbnails_dir)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    img.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
    path = thumbnails_dir / f"thumb_{uuid.uuid4().hex}.jpg"
    img.save(path, "JPEG", quality=92, optimize=True)
    return path


def replace_thumbnail(db: Session, video: Video, new_path: Path) -> None:
    old_path = Path(video.thumbnail_path) if video.thumbnail_path else None
    video.thumbnail_path = str(new_path)
    db.commit()
    db.refresh(video)
    if old_path and old_path.exists() and old_path != new_path:
        try:
            old_path.unlink()
        except Exception as exc:
            logger.error("Impossible de supprimer l'ancienne miniature %s : %s", old_path, exc)


def _owned_files(video: Video) -> list[tuple[str, str]]:
    files: list[tuple[str, str]] = []
    if video.file_path and video.storage_id is None:
        files.append(("fichier média", video.file_path))
    if video.thumbnail_path:
        files.append(("miniature", video.thumbnail_path))
    files.append(("mosaïque d'aperçu", str(storyboard_path(video.id))))
    return files + [("fichier de sous-titres", sub.file_path) for sub in video.subtitles]


def delete_video(db: Session, video: Video) -> None:
    """Retire la vidéo de la base (playlists, planning, chapitres) puis efface ses fichiers."""
    files = _owned_files(video)
    for item in list(video.playlist_items):
        db.delete(item)
    schedule_ids = drop_schedules_targeting(db, ScheduleTargetType.video, [video.id])
    web_path = video.web_path
    chapter_utils.drop_source(video)
    db.delete(video)
    db.commit()
    remove_jobs(schedule_ids)
    remove_web_file(web_path)
    for label, path in files:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception as exc:
            logger.error("Impossible de supprimer le %s %s : %s", label, path, exc)

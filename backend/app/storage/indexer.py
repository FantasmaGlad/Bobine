"""Indexation d'une bibliothèque externe : les médias du support sont enregistrés en base SANS être copiés.

Le support n'est lu qu'en lecture seule (ffprobe pour la durée, une image pour la miniature, les
étiquettes pour la radio). Tout ce que Bobine produit (miniatures, pochettes, base) reste sur le stockage
interne. Les médias qui exigent une conversion (transcodage) ne peuvent pas être lus directement : ils
sont signalés « à importer » plutôt que modifiés sur le support.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from app.storage import paths
from app.storage.transfer import KIND_TO_MEDIA, Plan, Unit, UnitFile

logger = logging.getLogger(__name__)


def mounted_path(root: str, rel: str) -> str:
    """Chemin enregistré en base : point de montage courant + chemin relatif (le même calcul que le remappage)."""
    return os.path.join(root, *rel.split("/"))


def plan_index(root: str, entries: list[dict[str, str]], kind: str) -> Plan:
    """Même sélection que l'import (sans contrôle d'espace ni d'historique d'import)."""
    from app.storage.transfer import plan_import

    return plan_import(root, entries, kind, source_id="", db=None, force=True)


def run_index_job(job_id: str, lib_id: int, root: str, plan: Plan, on_finished=lambda: None) -> dict[str, Any]:
    from app.database import SessionLocal
    from app.utils.executors import ffmpeg_executor
    from app.utils.import_jobs import JobCancelledError, is_job_cancelled, update_job
    from app.utils.ws_manager import manager as ws_manager

    summary: dict[str, Any] = {"indexed": 0, "skipped": list(plan.skipped), "failed": [], "needs_conversion": 0}
    update_job(job_id, stage="probing", files_total=len(plan.units), files_done=0, bytes_total=plan.total_bytes, bytes_done=0)
    first_result: int | None = None
    try:
        for index, unit in enumerate(plan.units):
            if is_job_cancelled(job_id):
                raise JobCancelledError(job_id)
            update_job(job_id, current_file=unit.title, files_done=index, progress_percent=round(100.0 * index / max(1, len(plan.units)), 1))
            try:
                with SessionLocal() as db:
                    if unit.kind == "video":
                        result = ffmpeg_executor.submit(_index_video, db, lib_id, root, unit).result()
                    elif unit.kind == "audio_course":
                        result = _index_audio_course(db, lib_id, root, unit)
                    else:
                        result = _index_radio(db, lib_id, root, unit)
                if result is None:
                    summary["skipped"].append({"path": unit.key, "reason": "already_indexed"})
                    continue
                if "reason" in result:
                    summary["skipped"].append({"path": unit.key, "reason": result["reason"]})
                    continue
                if result.get("needs_conversion"):
                    summary["needs_conversion"] += 1
                summary["indexed"] += result.get("count", 1)
                if first_result is None:
                    first_result = result["id"]
            except JobCancelledError:
                raise
            except Exception as exc:
                logger.warning("Indexation : %s : %s", unit.title, exc)
                summary["failed"].append({"path": unit.key, "code": "index_failed", "message": str(exc)})
        update_job(job_id, stage="done", result_id=first_result, details=summary, files_done=len(plan.units), progress_percent=100.0)
        if summary["indexed"]:
            ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_indexed"})
    except JobCancelledError:
        update_job(job_id, stage="cancelled", details=summary)
        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_indexed"})
    finally:
        on_finished()
    return summary


def _index_video(db, lib_id: int, root: str, unit: Unit):
    from app.config import settings
    from app.models import ImportSource, Video
    from app.utils.importer import _extract_metadata_or_unknown, parse_title_program_release
    from app.utils.video_utils import check_compatibility, generate_thumbnail

    f = unit.files[0]
    if db.query(Video.id).filter(Video.storage_id == lib_id, Video.rel_path == f.rel).first():
        return None
    name = os.path.basename(f.absolute)
    meta = _extract_metadata_or_unknown(f.absolute, name)
    if meta.get("is_drm"):
        return {"reason": "drm"}  # jamais de suppression de la source
    try:
        compat = check_compatibility(meta, f.absolute)
        needs_conversion = bool(compat["needs_normalization"])
    except Exception:
        needs_conversion = False
    thumbnail = None
    try:
        os.makedirs(settings.thumbnails_dir, exist_ok=True)
        thumbnail = generate_thumbnail(f.absolute, settings.thumbnails_dir, meta.get("duration_seconds"))
    except Exception as exc:
        logger.info("Miniature impossible pour %s : %s", name, exc)
    title, program, release = parse_title_program_release(name)
    video = Video(
        file_path=mounted_path(root, f.rel), title=title, program=program, release=release,
        duration_seconds=meta.get("duration_seconds"), width=meta.get("width"), height=meta.get("height"),
        codec=meta.get("codec"), thumbnail_path=thumbnail, source=ImportSource.upload,
        description=meta.get("description"), audio_channels=meta.get("audio_channels"),
        audio_codec=meta.get("audio_codec"), fps=meta.get("fps"), bitrate_kbps=meta.get("bitrate_kbps"),
        pix_fmt=meta.get("pix_fmt"), storage_id=lib_id, rel_path=f.rel,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return {"id": video.id, "needs_conversion": needs_conversion}


def _index_audio_course(db, lib_id: int, root: str, unit: Unit):
    from app.models import AudioCourse, AudioTrack
    from app.utils.audio_importer import _guess_program, _guess_release
    from app.utils.audio_utils import parse_track_number_and_title
    from app.utils.media_metadata import extract_audio_duration

    fresh = [f for f in unit.files if not db.query(AudioTrack.id).filter(AudioTrack.storage_id == lib_id, AudioTrack.rel_path == f.rel).first()]
    if not fresh:
        return None
    parsed = []
    for f in fresh:
        number, title = parse_track_number_and_title(os.path.basename(f.absolute))
        parsed.append((number, title, f))
    parsed.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0, t[2].rel))
    course = AudioCourse(title=unit.title, program=_guess_program(unit.title), release=_guess_release(unit.title))
    db.add(course)
    db.flush()
    for position, (number, title, f) in enumerate(parsed):
        db.add(AudioTrack(
            audio_course_id=course.id, number=number, title=title or f"Piste {position + 1}", file_path=mounted_path(root, f.rel),
            duration_seconds=extract_audio_duration(f.absolute), position=position, storage_id=lib_id, rel_path=f.rel,
        ))
    db.commit()
    return {"id": course.id, "count": len(parsed)}


def _index_radio(db, lib_id: int, root: str, unit: Unit):
    from app.config import settings
    from app.models import ImportSource, RadioCoverSource, RadioTrack
    from app.utils.media_metadata import extract_embedded_cover, extract_radio_metadata
    from app.utils.radio_utils import needs_transcode

    f = unit.files[0]
    if db.query(RadioTrack.id).filter(RadioTrack.storage_id == lib_id, RadioTrack.rel_path == f.rel).first():
        return None
    if needs_transcode(f.absolute):
        return {"reason": "format_requires_import"}  # transcoder exigerait d'écrire : à importer plutôt
    file_id = uuid.uuid4().hex
    meta = extract_radio_metadata(f.absolute)
    os.makedirs(settings.radio_covers_dir, exist_ok=True)
    cover = extract_embedded_cover(f.absolute, settings.radio_covers_dir, file_id)
    track = RadioTrack(
        file_path=mounted_path(root, f.rel), title=meta["title"], artist=meta["artist"], album=meta["album"],
        album_artist=meta["album_artist"], track_number=meta["track_number"], disc_number=meta["disc_number"],
        year=meta["year"], genre=meta["genre"], duration_seconds=meta["duration_seconds"], cover_path=cover,
        cover_source=RadioCoverSource.id3 if cover else RadioCoverSource.none, source=ImportSource.upload,
        storage_id=lib_id, rel_path=f.rel,
    )
    db.add(track)
    db.commit()
    db.refresh(track)
    return {"id": track.id}

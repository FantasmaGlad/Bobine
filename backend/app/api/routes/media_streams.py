"""Flux média servis avec plages HTTP : vidéos, fonds animés, pistes audio et radio, pochettes, rappels."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.responses import binary
from app.database import SessionLocal, get_db
from app.models import AudioTrack, Background, RadioAnnouncement, RadioTrack, Setting, Video
from app.storage import availability as storage_availability
from app.storage.service import service as storage_service
from app.utils.android_runtime import is_android
from app.utils.media_response import build_media_response
from app.utils.radio_utils import content_type_for
from app.utils.web_profile import choose_rendition, client_can_decode, parse_accept
from app.utils.web_rendition import request_web_rendition

logger = logging.getLogger(__name__)

router = APIRouter()

_IS_ANDROID = is_android()


def _storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "storage_unavailable", "message": "Ce média est sur un support externe actuellement débranché : rebranchez-le ou importez le média."},
        headers={"Retry-After": "5"},
    )


async def _range_stream_response(
    file_path: Path, request: Request, content_type: str, storage_id: int | None = None
) -> Response:
    if storage_id is None:
        return await build_media_response(file_path, request.headers, request.method, content_type)
    if not storage_availability.is_online(storage_id):
        raise _storage_unavailable()
    storage_service.touch_storage(storage_id)
    try:
        return await build_media_response(file_path, request.headers, request.method, content_type)
    except HTTPException as exc:
        if exc.status_code == 404:
            storage_service.request_refresh()
            raise _storage_unavailable() from exc
        raise


@router.head("/api/videos/{video_id}/stream", include_in_schema=False)
@router.get("/api/videos/{video_id}/stream", **binary("video/mp4", "video/webm"))
async def stream_video(
    video_id: int,
    request: Request,
    profile: str | None = None,
    accept: str | None = None,
    db: Session = Depends(get_db),
):
    """Flux d'une vidéo, avec négociation de la version lisible."""
    video = await run_in_threadpool(lambda: db.query(Video).filter(Video.id == video_id).first())
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    web_ready = bool(video.web_path) and video.web_status == "ready" and await run_in_threadpool(Path(video.web_path).exists)
    rendition = choose_rendition(
        issues=video.web_issues, web_ready=web_ready, profile=profile, accept=parse_accept(accept),
    )
    if rendition == "original" and not web_ready and accept is not None and video.web_status != "pending":
        parsed = parse_accept(accept) or set()
        if not client_can_decode(video.web_issues, parsed) and await run_in_threadpool(_auto_web_rendition_enabled, db):
            await run_in_threadpool(request_web_rendition, video.id)

    path = Path(video.web_path) if rendition == "web" else Path(video.file_path)
    response = await _range_stream_response(path, request, "video/mp4", video.storage_id if rendition != "web" else None)
    response.headers["X-Bobine-Rendition"] = rendition
    return response


def reset_stale_web_rendition_status() -> None:
    """Une version web « en cours » trouvée au démarrage ne peut venir que d'un arrêt brutal du processus."""
    db = SessionLocal()
    try:
        db.query(Video).filter(Video.web_status == "pending").update({Video.web_status: None})
        db.commit()
    except Exception as e:
        logger.warning(f"Réinitialisation des versions web en attente impossible : {e}")
    finally:
        db.close()


def _auto_web_rendition_enabled(db: Session) -> bool:
    row = db.query(Setting).filter(Setting.key == "auto_web_rendition").first()
    return bool(row and row.value == "true")


_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.head("/api/backgrounds/{background_id}/stream", include_in_schema=False)
@router.get("/api/backgrounds/{background_id}/stream", **binary("video/mp4", "image/jpeg", "image/png", "image/webp"))
async def stream_background(
    background_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    background = await run_in_threadpool(lambda: db.query(Background).filter(Background.id == background_id).first())
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    suffix = Path(background.file_path).suffix.lower()
    if suffix in _IMAGE_CONTENT_TYPES:
        return await _range_stream_response(Path(background.file_path), request, _IMAGE_CONTENT_TYPES[suffix])
    content_type = "video/webm" if suffix == ".webm" else "video/mp4"
    return await _range_stream_response(Path(background.file_path), request, content_type)


@router.head("/api/audio/tracks/{track_id}/stream", include_in_schema=False)
@router.get("/api/audio/tracks/{track_id}/stream", **binary("audio/mpeg", "audio/mp4", "audio/ogg"))
async def stream_audio_track(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    track = await run_in_threadpool(lambda: db.query(AudioTrack).filter(AudioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Piste audio non trouvée")
    return await _range_stream_response(Path(track.file_path), request, content_type_for(track.file_path), track.storage_id)


@router.head("/api/radio/tracks/{track_id}/stream", include_in_schema=False)
@router.get("/api/radio/tracks/{track_id}/stream", **binary("audio/mpeg", "audio/mp4", "audio/ogg"))
async def stream_radio_track(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Flux audio d'un morceau radio."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")
    return await _range_stream_response(Path(track.file_path), request, content_type_for(track.file_path), track.storage_id)


@router.head("/api/radio/tracks/{track_id}/cover", include_in_schema=False)
@router.get("/api/radio/tracks/{track_id}/cover", **binary("image/jpeg", "image/png", "image/webp"))
async def stream_radio_cover(
    track_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Pochette d'un morceau radio (JPEG normalisé, extrait ID3 ou uploadé)."""
    track = await run_in_threadpool(lambda: db.query(RadioTrack).filter(RadioTrack.id == track_id).first())
    if not track or not track.cover_path:
        raise HTTPException(status_code=404, detail="Pochette non trouvée")
    return await _range_stream_response(Path(track.cover_path), request, "image/jpeg")


@router.head("/api/radio/announcements/{announcement_id}/stream", include_in_schema=False)
@router.get("/api/radio/announcements/{announcement_id}/stream", **binary("audio/mpeg", "audio/mp4", "audio/ogg"))
async def stream_radio_announcement(
    announcement_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    """Flux audio d'un rappel."""
    announcement = await run_in_threadpool(lambda: db.query(RadioAnnouncement).filter(RadioAnnouncement.id == announcement_id).first())
    if not announcement:
        raise HTTPException(status_code=404, detail="Rappel non trouvé")
    return await _range_stream_response(Path(announcement.file_path), request, content_type_for(announcement.file_path))

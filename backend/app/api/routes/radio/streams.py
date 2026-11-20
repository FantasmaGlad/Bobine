"""Flux des morceaux radio, de leurs pochettes et des rappels."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.responses import binary
from app.api.stream_response import range_stream_response
from app.database import get_db
from app.models import RadioAnnouncement, RadioTrack
from app.radio.track_files import content_type_for

router = APIRouter()


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
    return await range_stream_response(Path(track.file_path), request, content_type_for(track.file_path), track.storage_id)


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
    return await range_stream_response(Path(track.cover_path), request, "image/jpeg")


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
    return await range_stream_response(Path(announcement.file_path), request, content_type_for(announcement.file_path))

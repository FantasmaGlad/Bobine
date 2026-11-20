"""Flux d'une piste de cours audio."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.responses import binary
from app.api.stream_response import range_stream_response
from app.database import get_db
from app.models import AudioTrack
from app.radio.track_files import content_type_for

router = APIRouter()


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
    return await range_stream_response(Path(track.file_path), request, content_type_for(track.file_path), track.storage_id)

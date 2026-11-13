"""État de lecture et reprise d'une lecture interrompue par une programmation."""

from datetime import datetime

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.responses import Message, PlaybackSnapshot
from app.database import get_db
from app.models import (
    PlaybackState,
    Playlist,
    Video,
)
from app.api.contract import DEFAULT_CHANNEL
from app.playback.manager import get_playback_manager
from app.scheduling.occurrences import ensure_utc, resolve_target_title

from .core import _resolve_channel, router
from .media_items import _thumbnail_filename


class InterruptedStateResponse(BaseModel):
    id: int
    cause: str | None
    channel: str | None = None
    interrupted_at: datetime
    video_id: int | None = None
    title: str | None = None
    position_seconds: float | None = None
    target_type: str | None = None
    target_id: int | None = None


@router.get("/api/playback/state", response_model=PlaybackSnapshot)
def get_playback_state(channel: str = DEFAULT_CHANNEL):
    """Snapshot ponctuel de l'état de lecture d'UN canal (utile au premier rendu, avant connexion WebSocket)."""
    return get_playback_manager(_resolve_channel(channel)).snapshot()


@router.get("/api/playback/interrupted", response_model=InterruptedStateResponse | None)
def get_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Dernière action différée en attente de reprise/relance explicite depuis l'interface, POUR UN CANAL DONNÉ."""
    resolved = _resolve_channel(channel)
    state = (
        db.query(PlaybackState)
        .filter(PlaybackState.channel == resolved)
        .order_by(PlaybackState.id.desc())
        .first()
    )
    if not state:
        return None

    if state.cause == "coach_priority":
        title, _program = resolve_target_title(db, state.target_type, state.target_id)
        return {
            "id": state.id,
            "cause": state.cause,
            "channel": state.channel,
            "interrupted_at": ensure_utc(state.interrupted_at),
            "target_type": state.target_type,
            "target_id": state.target_id,
            "title": title,
        }

    video = db.query(Video).filter(Video.id == state.video_id).first()
    return {
        "id": state.id,
        "cause": state.cause,
        "channel": state.channel,
        "interrupted_at": ensure_utc(state.interrupted_at),
        "video_id": state.video_id,
        "title": video.title if video else None,
        "position_seconds": state.position_seconds,
    }


@router.post("/api/playback/interrupted/resume", response_model=Message)
async def resume_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Relance l'action différée du canal : reprise à la position exacte pour une interruption par programmation, relance depuis zéro de la cible reportée par le mode coach."""
    resolved = _resolve_channel(channel)
    state = (
        db.query(PlaybackState)
        .filter(PlaybackState.channel == resolved)
        .order_by(PlaybackState.id.desc())
        .first()
    )
    if not state:
        raise HTTPException(status_code=404, detail="Aucune action différée à reprendre")

    manager = get_playback_manager(resolved)

    if state.cause == "coach_priority":
        if state.target_type == "video":
            video = db.query(Video).filter(Video.id == state.target_id).first()
            if not video:
                db.delete(state)
                db.commit()
                raise HTTPException(status_code=404, detail="La vidéo programmée n'existe plus dans la bibliothèque")
            await manager.load(
                video.id, video.title, video.duration_seconds, video.program,
                release=video.release, thumbnail_url=_thumbnail_filename(video.thumbnail_path),
                description=video.description, audio_channels=video.audio_channels,
                audio_codec=video.audio_codec, fps=video.fps, bitrate_kbps=video.bitrate_kbps,
                width=video.width, height=video.height,
            )
        else:
            playlist = db.query(Playlist).filter(Playlist.id == state.target_id).first()
            if not playlist:
                db.delete(state)
                db.commit()
                raise HTTPException(status_code=404, detail="La playlist programmée n'existe plus")
            sorted_items = sorted(playlist.items, key=lambda item: item.position)
            items_data = [
                {
                    "id": i.video.id, "title": i.video.title, "duration_seconds": i.video.duration_seconds,
                    "program": i.video.program, "release": i.video.release, "thumbnail_url": _thumbnail_filename(i.video.thumbnail_path),
                    "description": i.video.description, "audio_channels": i.video.audio_channels,
                    "audio_codec": i.video.audio_codec, "fps": i.video.fps, "bitrate_kbps": i.video.bitrate_kbps,
                    "width": i.video.width, "height": i.video.height,
                }
                for i in sorted_items
            ]
            await manager.load_playlist(playlist.id, playlist.name, items_data)

        db.delete(state)
        db.commit()
        return {"message": "Programmation relancée"}

    video = db.query(Video).filter(Video.id == state.video_id).first()
    if not video:
        db.delete(state)
        db.commit()
        raise HTTPException(status_code=404, detail="La vidéo interrompue n'existe plus dans la bibliothèque")

    await manager.load(
        video.id, video.title, video.duration_seconds, video.program,
        release=video.release, thumbnail_url=_thumbnail_filename(video.thumbnail_path),
        description=video.description, audio_channels=video.audio_channels,
        audio_codec=video.audio_codec, fps=video.fps, bitrate_kbps=video.bitrate_kbps,
        width=video.width, height=video.height,
    )
    await manager.seek(state.position_seconds or 0.0)

    db.delete(state)
    db.commit()
    return {"message": "Lecture reprise"}


@router.delete("/api/playback/interrupted", response_model=Message)
def dismiss_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Abandonne la lecture interrompue du canal sans la relancer."""
    state = (
        db.query(PlaybackState)
        .filter(PlaybackState.channel == _resolve_channel(channel))
        .order_by(PlaybackState.id.desc())
        .first()
    )
    if state:
        db.delete(state)
        db.commit()
    return {"message": "Lecture interrompue abandonnée"}

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
from app.videos.describe import playlist_video_items, video_details

from .core import _resolve_channel, router


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


def _latest_state(db: Session, channel: str) -> PlaybackState | None:
    return db.query(PlaybackState).filter(PlaybackState.channel == channel).order_by(PlaybackState.id.desc()).first()


def _discard(db: Session, state: PlaybackState) -> None:
    db.delete(state)
    db.commit()


@router.get("/api/playback/state", response_model=PlaybackSnapshot)
def get_playback_state(channel: str = DEFAULT_CHANNEL):
    """Snapshot ponctuel de l'état de lecture d'UN canal (utile au premier rendu, avant connexion WebSocket)."""
    return get_playback_manager(_resolve_channel(channel)).snapshot()


@router.get("/api/playback/interrupted", response_model=InterruptedStateResponse | None)
def get_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Dernière action différée en attente de reprise/relance explicite depuis l'interface, POUR UN CANAL DONNÉ."""
    state = _latest_state(db, _resolve_channel(channel))
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


def _require(db: Session, state: PlaybackState, model, target_id: int | None, missing: str):
    target = db.query(model).filter(model.id == target_id).first()
    if not target:
        _discard(db, state)
        raise HTTPException(status_code=404, detail=missing)
    return target


async def _relaunch_postponed(db: Session, state: PlaybackState, manager) -> None:
    if state.target_type == "video":
        video = _require(db, state, Video, state.target_id, "La vidéo programmée n'existe plus dans la bibliothèque")
        await manager.load(video.id, video.title, video.duration_seconds, video.program, **video_details(video))
        return
    playlist = _require(db, state, Playlist, state.target_id, "La playlist programmée n'existe plus")
    await manager.load_playlist(playlist.id, playlist.name, playlist_video_items(playlist))


async def _resume_video(db: Session, state: PlaybackState, manager) -> None:
    video = _require(db, state, Video, state.video_id, "La vidéo interrompue n'existe plus dans la bibliothèque")
    await manager.load(video.id, video.title, video.duration_seconds, video.program, **video_details(video))
    await manager.seek(state.position_seconds or 0.0)


@router.post("/api/playback/interrupted/resume", response_model=Message)
async def resume_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Relance l'action différée du canal : reprise à la position exacte pour une interruption par programmation, relance depuis zéro de la cible reportée par le mode coach."""
    resolved = _resolve_channel(channel)
    state = _latest_state(db, resolved)
    if not state:
        raise HTTPException(status_code=404, detail="Aucune action différée à reprendre")
    manager = get_playback_manager(resolved)
    postponed = state.cause == "coach_priority"
    if postponed:
        await _relaunch_postponed(db, state, manager)
    else:
        await _resume_video(db, state, manager)
    _discard(db, state)
    return {"message": "Programmation relancée" if postponed else "Lecture reprise"}


@router.delete("/api/playback/interrupted", response_model=Message)
def dismiss_interrupted_state(channel: str = DEFAULT_CHANNEL, db: Session = Depends(get_db)):
    """Abandonne la lecture interrompue du canal sans la relancer."""
    state = _latest_state(db, _resolve_channel(channel))
    if state:
        _discard(db, state)
    return {"message": "Lecture interrompue abandonnée"}

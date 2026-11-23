"""Mosaïque d'aperçu d'une vidéo pour la barre de lecture (générée en arrière-plan, voir app/videos/storyboard.py)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.videos.storyboard import is_stale, storyboard_path
from app.videos.storyboard_layout import storyboard_layout

from .lookup import video_or_404

router = APIRouter()


class StoryboardResponse(BaseModel):
    url: str
    interval_seconds: int
    count: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int


@router.get("/{video_id}/storyboard", response_model=StoryboardResponse)
def get_storyboard(video_id: int, db: Session = Depends(get_db)):
    """Mosaïque d'aperçu (une vignette par intervalle, lignes de gauche à droite) ; 404 tant qu'elle n'est pas prête."""
    video = video_or_404(db, video_id)
    layout = storyboard_layout(video.duration_seconds)
    path = storyboard_path(video.id)
    if layout is None or not path.exists() or is_stale(video.id, video.file_path):
        raise HTTPException(status_code=404, detail={"code": "storyboard_not_ready", "message": "Mosaïque d'aperçu pas encore prête."})
    return StoryboardResponse(url=f"/api/thumbnails/storyboards/{path.name}?v={int(path.stat().st_mtime)}", **layout.__dict__)

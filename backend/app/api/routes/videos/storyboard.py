"""Mosaïque d'aperçu d'une vidéo pour la barre de lecture (générée en arrière-plan, voir app/videos/storyboard.py)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.videos.storyboard import is_stale, sheet_path
from app.videos.storyboard_layout import storyboard_layout

from .lookup import video_or_404

router = APIRouter()


class StoryboardResponse(BaseModel):
    sheets: List[str]
    interval_seconds: int
    count: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int


@router.get("/{video_id}/storyboard", response_model=StoryboardResponse)
def get_storyboard(video_id: int, db: Session = Depends(get_db)):
    """Planches d'aperçu (une vignette par intervalle, planches de colonnes x lignes, de gauche à droite) ; 404 tant qu'elles ne sont pas prêtes."""
    video = video_or_404(db, video_id)
    layout = storyboard_layout(video.duration_seconds)
    paths = [sheet_path(video.id, n) for n in range(layout.sheets)] if layout else []
    if layout is None or not all(path.exists() for path in paths) or is_stale(video.id, video.file_path):
        raise HTTPException(status_code=404, detail={"code": "storyboard_not_ready", "message": "Planches d'aperçu pas encore prêtes."})
    version = int(paths[0].stat().st_mtime)
    sheets = [f"/api/thumbnails/storyboards/{video.id}/{path.name}?v={version}" for path in paths]
    return StoryboardResponse(sheets=sheets, **{k: v for k, v in layout.__dict__.items() if k != "sheets"})

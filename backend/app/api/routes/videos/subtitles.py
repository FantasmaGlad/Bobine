"""Pistes de sous-titres d'une vidéo."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.responses import Message, binary
from app.database import get_db
from app.utils.subtitles import MAX_SUBTITLE_BYTES
from app.utils.ws_manager import manager as ws_manager
from app.videos.subtitles import SubtitleRejected, delete_subtitle as remove_subtitle, save_uploaded_subtitle

from .lookup import subtitle_or_404, video_or_404
from .schemas import VideoSubtitleResponse, subtitle_response

router = APIRouter()


@router.get("/{video_id}/subtitles", response_model=List[VideoSubtitleResponse])
def list_subtitles(video_id: int, db: Session = Depends(get_db)):
    """Liste les pistes de sous-titres associées à une vidéo."""
    return [subtitle_response(sub) for sub in video_or_404(db, video_id).subtitles]


@router.post("/{video_id}/subtitles", response_model=VideoSubtitleResponse)
async def upload_subtitle(
    video_id: int,
    file: UploadFile = File(...),
    language_code: str | None = Form(None),
    language_label: str | None = Form(None),
    db: Session = Depends(get_db),
):
    """Importe un fichier .srt ou .vtt pour une vidéo, le convertit en WebVTT si nécessaire et l'enregistre."""
    video_or_404(db, video_id)
    content = await file.read(MAX_SUBTITLE_BYTES + 1)
    try:
        sub = save_uploaded_subtitle(db, video_id, file.filename or "subtitles.srt", content, language_code, language_label)
    except SubtitleRejected as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)
    await ws_manager.broadcast({"type": "library_change"})
    return subtitle_response(sub)


@router.delete("/{video_id}/subtitles/{subtitle_id}", response_model=Message)
async def delete_subtitle(video_id: int, subtitle_id: int, db: Session = Depends(get_db)):
    """Supprime une piste de sous-titres sur disque et en base."""
    remove_subtitle(db, subtitle_or_404(db, video_id, subtitle_id))
    await ws_manager.broadcast({"type": "library_change"})
    return {"message": "Sous-titre supprimé"}


@router.get("/{video_id}/subtitles/{subtitle_id}/vtt", **binary("text/vtt"))
def get_subtitle_vtt(video_id: int, subtitle_id: int, db: Session = Depends(get_db)):
    """Sert le fichier WebVTT pour les balises HTML5 <track> avec les bons en-têtes CORS et Content-Type."""
    path = Path(subtitle_or_404(db, video_id, subtitle_id).file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier de sous-titres manquant sur disque")
    return FileResponse(
        str(path),
        media_type="text/vtt; charset=utf-8",
        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=3600"},
    )

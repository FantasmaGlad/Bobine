"""Lecture d'une vidéo ou d'une piste de sous-titres, 404 si elle n'existe pas."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Video, VideoSubtitle


def video_or_404(db: Session, video_id: int) -> Video:
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    return video


def subtitle_or_404(db: Session, video_id: int, subtitle_id: int) -> VideoSubtitle:
    sub = db.query(VideoSubtitle).filter(VideoSubtitle.id == subtitle_id, VideoSubtitle.video_id == video_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Piste de sous-titres non trouvée")
    return sub

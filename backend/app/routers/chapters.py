"""Chapitres des cours : lecture, remplacement, import (JSON, WebVTT, texte,
chapitres incorporés au fichier) et export."""

import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Video, VideoChapter
from app.utils import chapters as chapter_utils
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["chapters"])


class ChapterIn(BaseModel):
    start_seconds: float
    end_seconds: float | None = None
    title: str


class ChaptersPayload(BaseModel):
    chapters: List[ChapterIn]


class ChapterResponse(BaseModel):
    id: int
    position: int
    start_seconds: float
    end_seconds: float | None = None
    title: str


def _get_video(db: Session, video_id: int) -> Video:
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")
    return video


def _serialize(video: Video) -> list[ChapterResponse]:
    return [
        ChapterResponse(id=c.id, position=c.position, start_seconds=c.start_seconds, end_seconds=c.end_seconds, title=c.title)
        for c in video.chapters
    ]


def _replace(db: Session, video: Video, raw: list[dict]) -> list[ChapterResponse]:
    try:
        cleaned = chapter_utils.normalize(raw, video.duration_seconds)
    except chapter_utils.ChapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    video.chapters.clear()
    db.flush()
    for position, item in enumerate(cleaned):
        video.chapters.append(
            VideoChapter(
                position=position,
                start_seconds=item["start_seconds"],
                end_seconds=item["end_seconds"],
                title=item["title"],
            )
        )
    db.commit()
    db.refresh(video)
    return _serialize(video)


@router.get("/{video_id}/chapters", response_model=List[ChapterResponse])
def list_chapters(video_id: int, db: Session = Depends(get_db)):
    return _serialize(_get_video(db, video_id))


@router.put("/{video_id}/chapters", response_model=List[ChapterResponse])
async def replace_chapters(video_id: int, payload: ChaptersPayload, db: Session = Depends(get_db)):
    """Remplace tous les chapitres du cours (liste vide = les supprimer)."""
    video = _get_video(db, video_id)
    raw = [{"start_seconds": c.start_seconds, "end_seconds": c.end_seconds, "title": c.title} for c in payload.chapters]
    result = _replace(db, video, raw)
    await ws_manager.broadcast({"type": "library_change"})
    return result


@router.post("/{video_id}/chapters/import", response_model=List[ChapterResponse])
async def import_chapters(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Importe un fichier de chapitres (.json, .vtt ou texte « 05:00 Titre ») et remplace ceux du cours."""
    video = _get_video(db, video_id)
    content = await file.read(chapter_utils.MAX_CHAPTER_BYTES + 1)
    if len(content) > chapter_utils.MAX_CHAPTER_BYTES:
        raise HTTPException(status_code=413, detail="Fichier de chapitres trop volumineux (256 Ko maximum).")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")
    try:
        raw = chapter_utils.parse_any(text, file.filename or "")
    except chapter_utils.ChapterError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    result = _replace(db, video, raw)
    await ws_manager.broadcast({"type": "library_change"})
    return result


@router.post("/{video_id}/chapters/from-file", response_model=List[ChapterResponse])
async def import_embedded_chapters(video_id: int, db: Session = Depends(get_db)):
    """Lit les chapitres incorporés à la vidéo (MKV, MP4) et remplace ceux du cours."""
    video = _get_video(db, video_id)
    raw = await run_in_threadpool(chapter_utils.read_embedded, video.file_path)
    if not raw:
        raise HTTPException(status_code=404, detail="Aucun chapitre incorporé dans ce fichier vidéo.")
    result = _replace(db, video, raw)
    await ws_manager.broadcast({"type": "library_change"})
    return result


@router.get("/{video_id}/chapters/export")
def export_chapters(video_id: int, db: Session = Depends(get_db)):
    """Chapitres au format d'import JSON (téléchargeable)."""
    video = _get_video(db, video_id)
    body = {
        "version": 1,
        "chapters": [
            {"start": c.start_seconds, **({"end": c.end_seconds} if c.end_seconds is not None else {}), "title": c.title}
            for c in video.chapters
        ],
    }
    return JSONResponse(body, headers={"Content-Disposition": f'attachment; filename="chapitres-{video_id}.json"'})

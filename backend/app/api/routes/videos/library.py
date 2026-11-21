"""Bibliothèque vidéo : liste, détail, modification, suppression, version web, miniature, normalisation."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.contract import SORT_ORDERS, VIDEO_SORT_FIELDS, regex
from app.api.paging import Window, window
from app.api.responses import Message
from app.database import get_db
from app.utils._pydantic_compat import pattern_arg
from app.utils.executors import ffmpeg_executor
from app.utils.video_utils.compatibility import check_compatibility
from app.utils.video_utils.probe import extract_metadata
from app.utils.web_rendition import remove_web_file, request_web_rendition
from app.videos.events import notify_library
from app.videos.files import delete_video as remove_video
from app.videos.files import rename_video_file, replace_thumbnail, write_manual_thumbnail
from app.videos.normalize import bg_normalize
from app.videos.query import program_names, video_query

from .lookup import video_or_404
from .schemas import ImportJobAccepted, VideoResponse, VideoUpdate

router = APIRouter()

_EXTERNAL_READ_ONLY = {
    "code": "external_read_only",
    "message": "Ce cours est sur un support externe (lecture seule) : importez-le d'abord pour le convertir, ou créez sa version lisible partout.",
}


@router.get("", response_model=List[VideoResponse])
def list_videos(
    search: str | None = None,
    program: str | None = None,
    release: str | None = None,
    sort_by: str = Query("imported_at", **pattern_arg(regex(VIDEO_SORT_FIELDS))),
    order: str = Query("desc", **pattern_arg(regex(SORT_ORDERS))),
    db: Session = Depends(get_db),
    page: Window = Depends(window),
):
    """Récupère la liste des vidéos de la bibliothèque avec filtres et tris."""
    return page.rows(video_query(db, search, program, release, sort_by, order))


@router.get("/programs", response_model=List[str])
def list_programs(db: Session = Depends(get_db)):
    """Catégories (programmes) réellement présentes dans la bibliothèque, triées."""
    return program_names(db)


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: int, db: Session = Depends(get_db)):
    """Récupère les détails d'une vidéo spécifique."""
    return video_or_404(db, video_id)


@router.put("/{video_id}", response_model=VideoResponse)
def update_video(video_id: int, payload: VideoUpdate, db: Session = Depends(get_db)):
    """Met à jour les métadonnées modifiables d'une vidéo (titre, programme, release)."""
    video = video_or_404(db, video_id)
    if payload.title is not None and not payload.title.strip():
        raise HTTPException(status_code=422, detail="Le titre ne peut pas être vide")
    if payload.title is not None and payload.title != video.title:
        rename_video_file(video, payload.title)
        video.title = payload.title
    if payload.program is not None:
        video.program = payload.program
    if payload.release is not None:
        video.release = payload.release
    if payload.description is not None:
        video.description = payload.description.strip() or None
    db.commit()
    db.refresh(video)
    notify_library("video_updated")
    return video


@router.delete("/{video_id}", response_model=Message)
def delete_video(video_id: int, db: Session = Depends(get_db)):
    """Supprime physiquement les fichiers de la vidéo et de sa miniature, puis supprime son entrée en BDD."""
    remove_video(db, video_or_404(db, video_id))
    notify_library("video_deleted")
    return {"message": "Vidéo supprimée avec succès"}


@router.post("/{video_id}/web-rendition", response_model=ImportJobAccepted, status_code=202)
def create_web_rendition(video_id: int, db: Session = Depends(get_db)):
    """Lance la production de la version « lisible partout » (H.264 8 bits, ≤ 1080p, AAC) — suivie via `GET /api/import-jobs`, état dans `web_status`."""
    if video_or_404(db, video_id).web_safe:
        raise HTTPException(status_code=409, detail="Cette vidéo est déjà lisible sur tous les navigateurs : aucune version web n'est nécessaire.")
    job_id = request_web_rendition(video_id)
    if job_id is None:
        raise HTTPException(status_code=409, detail="Une version web est déjà en cours de production pour cette vidéo.")
    return {"job_id": job_id}


@router.delete("/{video_id}/web-rendition", response_model=Message)
def delete_web_rendition(video_id: int, db: Session = Depends(get_db)):
    video = video_or_404(db, video_id)
    remove_web_file(video.web_path)
    video.web_path, video.web_status = None, None
    db.commit()
    notify_library("web_rendition_deleted")
    return {"message": "Version web supprimée"}


@router.put("/{video_id}/thumbnail", response_model=VideoResponse)
async def upload_video_thumbnail(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Miniature manuelle."""
    video = video_or_404(db, video_id)
    try:
        new_path = await run_in_threadpool(write_manual_thumbnail, file.file)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fichier image invalide")
    replace_thumbnail(db, video, new_path)
    notify_library("thumbnail_changed")
    return video


@router.post("/{video_id}/normalize", response_model=Message)
def manual_normalize(video_id: int, db: Session = Depends(get_db)):
    """Déclenche manuellement la normalisation d'une vidéo si elle n'est pas Direct Play."""
    video = video_or_404(db, video_id)
    if video.storage_id is not None:
        raise HTTPException(status_code=409, detail=_EXTERNAL_READ_ONLY)
    try:
        meta = extract_metadata(video.file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Impossible d'analyser la vidéo : {e}")
    compat = check_compatibility(meta, video.file_path)
    if not compat["needs_normalization"]:
        return {"message": "La vidéo est déjà compatible Direct Play, aucune action requise."}
    ffmpeg_executor.submit(bg_normalize, video_id, compat["actions"], meta)
    return {"message": "La tâche de normalisation a été démarrée en tâche de fond."}

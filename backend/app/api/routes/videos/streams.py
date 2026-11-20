"""Flux d'une vidéo, avec négociation de la version lisible."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.responses import binary
from app.api.stream_response import range_stream_response
from app.database import SessionLocal, get_db
from app.models import Setting, Video
from app.utils.web_profile import choose_rendition, client_can_decode, parse_accept
from app.utils.web_rendition import request_web_rendition

logger = logging.getLogger(__name__)

router = APIRouter()


@router.head("/api/videos/{video_id}/stream", include_in_schema=False)
@router.get("/api/videos/{video_id}/stream", **binary("video/mp4", "video/webm"))
async def stream_video(
    video_id: int,
    request: Request,
    profile: str | None = None,
    accept: str | None = None,
    db: Session = Depends(get_db),
):
    """Flux d'une vidéo, avec négociation de la version lisible."""
    video = await run_in_threadpool(lambda: db.query(Video).filter(Video.id == video_id).first())
    if not video:
        raise HTTPException(status_code=404, detail="Vidéo non trouvée")

    web_ready = bool(video.web_path) and video.web_status == "ready" and await run_in_threadpool(Path(video.web_path).exists)
    rendition = choose_rendition(
        issues=video.web_issues, web_ready=web_ready, profile=profile, accept=parse_accept(accept),
    )
    if rendition == "original" and not web_ready and accept is not None and video.web_status != "pending":
        parsed = parse_accept(accept) or set()
        if not client_can_decode(video.web_issues, parsed) and await run_in_threadpool(_auto_web_rendition_enabled, db):
            await run_in_threadpool(request_web_rendition, video.id)

    path = Path(video.web_path) if rendition == "web" else Path(video.file_path)
    response = await range_stream_response(path, request, "video/mp4", video.storage_id if rendition != "web" else None)
    response.headers["X-Bobine-Rendition"] = rendition
    return response


def reset_stale_web_rendition_status() -> None:
    """Une version web « en cours » trouvée au démarrage ne peut venir que d'un arrêt brutal du processus."""
    db = SessionLocal()
    try:
        db.query(Video).filter(Video.web_status == "pending").update({Video.web_status: None})
        db.commit()
    except Exception as e:
        logger.warning(f"Réinitialisation des versions web en attente impossible : {e}")
    finally:
        db.close()


def _auto_web_rendition_enabled(db: Session) -> bool:
    row = db.query(Setting).filter(Setting.key == "auto_web_rendition").first()
    return bool(row and row.value == "true")

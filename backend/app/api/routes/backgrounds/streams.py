"""Flux d'un fond animé, vidéo ou image."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.responses import binary
from app.api.stream_response import range_stream_response
from app.database import get_db
from app.models import Background

router = APIRouter()

_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


@router.head("/api/backgrounds/{background_id}/stream", include_in_schema=False)
@router.get("/api/backgrounds/{background_id}/stream", **binary("video/mp4", "image/jpeg", "image/png", "image/webp", "image/gif"))
async def stream_background(
    background_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    background = await run_in_threadpool(lambda: db.query(Background).filter(Background.id == background_id).first())
    if not background:
        raise HTTPException(status_code=404, detail="Fond animé non trouvé")
    suffix = Path(background.file_path).suffix.lower()
    if suffix in _IMAGE_CONTENT_TYPES:
        return await range_stream_response(Path(background.file_path), request, _IMAGE_CONTENT_TYPES[suffix])
    content_type = "video/webm" if suffix == ".webm" else "video/mp4"
    return await range_stream_response(Path(background.file_path), request, content_type)

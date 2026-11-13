from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.contract import MEDIA_KINDS, regex
from app.catalog.search import catalog
from app.database import get_db
from app.utils._pydantic_compat import pattern_arg

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaEntry(BaseModel):
    kind: str
    id: int
    title: str
    subtitle: str | None = None
    duration_seconds: float | None = None
    available: bool


class MediaPage(BaseModel):
    items: list[MediaEntry]
    total: int
    limit: int
    offset: int


@router.get("", response_model=MediaPage)
async def list_media(
    kind: str | None = Query(None, **pattern_arg(regex(MEDIA_KINDS))),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> MediaPage:
    """Médias de toutes les bibliothèques avec leur identifiant de lecture, filtrés et paginés."""
    entries, total = await run_in_threadpool(catalog, db, (kind,) if kind else MEDIA_KINDS, q, limit, offset)
    return MediaPage(items=[MediaEntry(**entry.as_dict()) for entry in entries], total=total, limit=limit, offset=offset)

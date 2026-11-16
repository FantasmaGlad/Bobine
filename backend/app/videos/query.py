"""Requêtes de la bibliothèque vidéo : liste filtrée et triée, programmes présents."""

from __future__ import annotations

from sqlalchemy.orm import Query, Session

from app.models import Video

_SORT_COLUMNS = {"title": Video.title, "duration": Video.duration_seconds}


def video_query(db: Session, search: str | None, program: str | None, release: str | None, sort_by: str, order: str) -> Query:
    query = db.query(Video)
    if search:
        query = query.filter(Video.title.ilike(f"%{search}%"))
    if program:
        query = query.filter(Video.program == program)
    if release:
        query = query.filter(Video.release == release)
    col = _SORT_COLUMNS.get(sort_by, Video.imported_at)
    if order == "asc":
        return query.order_by(col.asc(), Video.id.asc())
    return query.order_by(col.desc(), Video.id.desc())


def program_names(db: Session) -> list[str]:
    rows = db.query(Video.program).filter(Video.program.isnot(None), Video.program != "").distinct().all()
    return sorted({r[0] for r in rows}, key=str.casefold)

"""API des pistes de la bibliothèque musicale : liste, fiche, modification, pochette, suppression."""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.api.paging import Window, window
from app.api.responses import Message
from app.config import settings
from app.database import get_db
from app.models import RadioTag, RadioTrack
from app.utils._pydantic_compat import fields_set
from app.utils.radio_utils import save_cover_image

from .schemas import RadioTrackResponse, RadioTrackUpdate, track_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tracks", response_model=List[RadioTrackResponse])
def list_tracks(
    q: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    genre: str | None = None,
    tag: str | None = None,
    db: Session = Depends(get_db),
    page: Window = Depends(window),
):
    """Liste filtrable des morceaux (vue « Morceaux » + filtres artiste/album/ genre/tag des autres vues)."""
    query = db.query(RadioTrack).options(selectinload(RadioTrack.tags))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(RadioTrack.title.ilike(like), RadioTrack.artist.ilike(like), RadioTrack.album.ilike(like))
        )
    if artist:
        query = query.filter(or_(RadioTrack.artist == artist, RadioTrack.album_artist == artist))
    if album:
        query = query.filter(RadioTrack.album == album)
    if genre:
        query = query.filter(RadioTrack.genre == genre)
    if tag:
        query = query.join(RadioTrack.tags).filter(RadioTag.name == tag)

    query = query.order_by(
        func.coalesce(RadioTrack.album_artist, RadioTrack.artist).asc(),
        RadioTrack.album.asc(),
        RadioTrack.disc_number.asc(),
        RadioTrack.track_number.asc(),
        RadioTrack.title.asc(),
        RadioTrack.id.asc(),
    )
    return [track_response(t) for t in page.rows(query)]


@router.get("/tracks/{track_id}", response_model=RadioTrackResponse)
def get_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(RadioTrack).filter(RadioTrack.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")
    return track_response(track)


def _apply_tags(db: Session, track: RadioTrack, tag_names: List[str]) -> None:
    resolved: list[RadioTag] = []
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag = db.query(RadioTag).filter(RadioTag.name == name).first()
        if not tag:
            tag = RadioTag(name=name)
            db.add(tag)
            db.flush()
        if tag not in resolved:
            resolved.append(tag)
    track.tags = resolved


@router.put("/tracks/{track_id}", response_model=RadioTrackResponse)
def update_track(track_id: int, payload: RadioTrackUpdate, db: Session = Depends(get_db)):
    """Édition manuelle des métadonnées et des tags."""
    track = db.query(RadioTrack).filter(RadioTrack.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")

    provided = fields_set(payload)
    text_fields = ("title", "artist", "album", "album_artist", "genre")
    for field in text_fields:
        if field in provided:
            value = getattr(payload, field)
            setattr(track, field, value.strip() if value and value.strip() else None)
    if "title" in provided and not track.title:
        raise HTTPException(status_code=422, detail="Le titre ne peut pas être vide")
    for field in ("track_number", "disc_number", "year"):
        if field in provided:
            setattr(track, field, getattr(payload, field))
    if payload.tags is not None:
        _apply_tags(db, track, payload.tags)

    db.commit()
    db.refresh(track)
    return track_response(track)


@router.post("/tracks/{track_id}/cover", response_model=RadioTrackResponse)
def upload_track_cover(track_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Pochette fournie manuellement : remplace la pochette existante."""
    from app.models import RadioCoverSource

    track = db.query(RadioTrack).filter(RadioTrack.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "").suffix)
    try:
        shutil.copyfileobj(file.file, tmp)
        tmp.close()
        import uuid
        file_id = uuid.uuid4().hex
        try:
            new_cover = save_cover_image(tmp.name, settings.radio_covers_dir, file_id)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Image invalide : {e}")
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass

    old_cover = track.cover_path
    track.cover_path = new_cover
    track.cover_source = RadioCoverSource.manual
    db.commit()
    db.refresh(track)
    if old_cover and old_cover != new_cover and Path(old_cover).exists():
        try:
            os.remove(old_cover)
        except OSError:
            pass
    return track_response(track)


@router.delete("/tracks/{track_id}", response_model=Message)
def delete_track(track_id: int, db: Session = Depends(get_db)):
    track = db.query(RadioTrack).filter(RadioTrack.id == track_id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Morceau non trouvé")

    file_path = track.file_path if track.storage_id is None else None
    cover_path = track.cover_path
    db.delete(track)
    db.commit()

    for path in (file_path, cover_path):
        if path and Path(path).exists():
            try:
                os.remove(path)
            except OSError as e:
                logger.error(f"Suppression de fichier radio impossible ({path}) : {e}")
    return {"message": "Morceau supprimé"}

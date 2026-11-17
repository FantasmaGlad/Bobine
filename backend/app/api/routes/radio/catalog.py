"""API du catalogue musical : artistes, albums et étiquettes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.responses import Message, RadioAlbum, RadioArtist, RadioTagCount, RadioTagEntry
from app.database import get_db
from app.models import RadioTag, RadioTrack, radio_track_tags

from .schemas import TagInput

router = APIRouter()


@router.get("/artists", response_model=List[RadioArtist])
def list_artists(db: Session = Depends(get_db)):
    """Artistes dérivés par regroupement (album_artist sinon artist)."""
    name_col = func.coalesce(RadioTrack.album_artist, RadioTrack.artist)
    rows = (
        db.query(
            name_col.label("name"),
            func.count(RadioTrack.id).label("track_count"),
            func.count(func.distinct(RadioTrack.album)).label("album_count"),
        )
        .filter(name_col.isnot(None))
        .group_by(name_col)
        .order_by(name_col.asc())
        .all()
    )
    return [{"name": r.name, "track_count": r.track_count, "album_count": r.album_count} for r in rows]


@router.get("/albums", response_model=List[RadioAlbum])
def list_albums(db: Session = Depends(get_db)):
    """Albums dérivés par regroupement (album_artist, album)."""
    albums: dict[tuple, dict] = {}
    tracks = (
        db.query(RadioTrack)
        .filter(RadioTrack.album.isnot(None))
        .order_by(RadioTrack.disc_number.asc(), RadioTrack.track_number.asc())
        .all()
    )
    for t in tracks:
        artist = t.album_artist or t.artist
        key = (artist, t.album)
        entry = albums.setdefault(key, {
            "album": t.album, "album_artist": artist, "track_count": 0,
            "year": t.year, "cover_track_id": None,
        })
        entry["track_count"] += 1
        if entry["cover_track_id"] is None and t.cover_path is not None:
            entry["cover_track_id"] = t.id
        if entry["year"] is None and t.year is not None:
            entry["year"] = t.year
    return sorted(albums.values(), key=lambda a: ((a["album_artist"] or "").lower(), (a["album"] or "").lower()))


@router.get("/tags", response_model=List[RadioTagCount])
def list_tags(db: Session = Depends(get_db)):
    rows = (
        db.query(RadioTag.id, RadioTag.name, func.count(radio_track_tags.c.radio_track_id).label("track_count"))
        .outerjoin(radio_track_tags, RadioTag.id == radio_track_tags.c.tag_id)
        .group_by(RadioTag.id, RadioTag.name)
        .order_by(RadioTag.name.asc())
        .all()
    )
    return [{"id": r.id, "name": r.name, "track_count": r.track_count} for r in rows]


@router.post("/tags", response_model=RadioTagEntry)
def create_tag(payload: TagInput, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Le nom du tag est requis")
    if db.query(RadioTag).filter(RadioTag.name == name).first():
        raise HTTPException(status_code=409, detail="Ce tag existe déjà")
    tag = RadioTag(name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return {"id": tag.id, "name": tag.name}


@router.put("/tags/{tag_id}", response_model=RadioTagEntry)
def rename_tag(tag_id: int, payload: TagInput, db: Session = Depends(get_db)):
    tag = db.query(RadioTag).filter(RadioTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag non trouvé")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Le nom du tag est requis")
    existing = db.query(RadioTag).filter(RadioTag.name == name, RadioTag.id != tag_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Ce tag existe déjà")
    tag.name = name
    db.commit()
    return {"id": tag.id, "name": tag.name}


@router.delete("/tags/{tag_id}", response_model=Message)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(RadioTag).filter(RadioTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag non trouvé")
    db.delete(tag)
    db.commit()
    return {"message": "Tag supprimé"}

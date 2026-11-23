"""Diffusion d'un visuel : boucle ordonnée d'images et de vidéos par canal."""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.contract import CHANNELS, DEFAULT_CHANNEL, regex
from app.api.responses import SignageLoop
from app.database import get_db
from app.models import Visual
from app.signage import store
from app.signage.playlist import SignageItem, parse_items, resolved_seconds
from app.utils._pydantic_compat import pattern_arg
from app.utils.ws_manager import manager as ws_manager

router = APIRouter(prefix="/api/signage", tags=["signage"])


class SignageUpdate(BaseModel):
    channel: str = DEFAULT_CHANNEL
    items: List[Any]


def _payload(db: Session, channel: str, items: tuple[SignageItem, ...]) -> dict:
    ids = {item.visual_id for item in items}
    visuals = {row.id: row for row in db.query(Visual).filter(Visual.id.in_(ids))} if ids else {}
    entries = []
    for item in items:
        visual = visuals.get(item.visual_id)
        if visual is None:
            continue
        entries.append({
            "visual_id": item.visual_id,
            "seconds": item.seconds,
            "title": visual.title,
            "is_image": visual.is_image,
            "play_seconds": resolved_seconds(item, visual.is_image),
            "duration_seconds": visual.duration_seconds,
        })
    return {"channel": channel, "items": entries}


def _check_channel(channel: str) -> str:
    if channel not in CHANNELS:
        raise HTTPException(status_code=422, detail=f"canal inconnu : {', '.join(CHANNELS)}")
    return channel


@router.get("", response_model=SignageLoop)
def get_signage(channel: str = Query(DEFAULT_CHANNEL, **pattern_arg(regex(CHANNELS))), db: Session = Depends(get_db)):
    """Boucle de visuels du canal, dans l'ordre de diffusion ; un visuel supprimé n'y figure plus."""
    return _payload(db, channel, store.load(db, channel))


@router.put("", response_model=SignageLoop)
async def put_signage(payload: SignageUpdate, db: Session = Depends(get_db)):
    """Remplace la boucle du canal ; `seconds` null : 10 s pour une image, la vidéo entière pour une vidéo."""
    channel = _check_channel(payload.channel)
    try:
        items = parse_items(payload.items)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    ids = {item.visual_id for item in items}
    known = {row.id for row in db.query(Visual.id).filter(Visual.id.in_(ids))} if ids else set()
    missing = sorted(ids - known)
    if missing:
        raise HTTPException(status_code=404, detail=f"visuel introuvable : {', '.join(map(str, missing))}")
    store.save(db, channel, items)
    await ws_manager.broadcast({"event": "signage_change", "channel": channel})
    return _payload(db, channel, items)

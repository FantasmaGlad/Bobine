"""API des sorties radio : état, son et ambiance par défaut."""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.responses import DefaultPlaylists, RadioSnapshot, RadioSound
from app.database import get_db
from app.models import RadioPlaylist

router = APIRouter()


@router.get("/state", response_model=RadioSnapshot)
def get_radio_state(channel: str | None = None):
    """Snapshot ponctuel de l'état d'UNE sortie radio."""
    from app.radio.manager import get_radio_manager

    return get_radio_manager(channel).snapshot()


@router.get("/sound", response_model=RadioSound)
def get_radio_sound(channel: str | None = None):
    """Réglages de son courants d'UNE sortie radio (réseau par défaut) : même valeur que le champ `sound` de l'état diffusé, pour les clients sans WebSocket."""
    from app.radio.manager import get_radio_manager

    return get_radio_manager(channel).state["sound"]


@router.put("/sound", response_model=RadioSound)
async def set_radio_sound(payload: dict = Body(...), channel: str | None = None, db: Session = Depends(get_db)):
    """Modifie les réglages de son d'UNE sortie radio."""
    from app.radio.manager import get_radio_manager
    from app.utils.radio_commands import apply_sound

    return await apply_sound(db, get_radio_manager(channel), payload)


class DefaultPlaylistInput(BaseModel):
    channel: str
    playlist_id: int | None = None


@router.get("/default-playlist", response_model=DefaultPlaylists)
def get_default_playlists(db: Session = Depends(get_db)):
    """Ambiance par défaut de chaque sortie radio."""
    from app.api.contract import RADIO_CHANNELS
    from app.scheduling.radio import get_radio_default_playlist_override, resolve_radio_default_playlist

    result = {}
    for radio_channel in RADIO_CHANNELS:
        effective = resolve_radio_default_playlist(db, radio_channel)
        result[radio_channel] = {
            "override_playlist_id": get_radio_default_playlist_override(db, radio_channel),
            "effective_playlist_id": effective.id if effective else None,
        }
    return result


@router.put("/default-playlist", response_model=DefaultPlaylists)
def set_default_playlist(payload: DefaultPlaylistInput, db: Session = Depends(get_db)):
    """Choisit l'ambiance par défaut d'UNE sortie radio (démarrage automatique, fin de fenêtre de planning, bascule de la sortie câblée sur Radio)."""
    from app.api.contract import RADIO_CHANNELS
    from app.scheduling.radio import set_radio_default_playlist_override

    if payload.channel not in RADIO_CHANNELS:
        raise HTTPException(status_code=422, detail="Sortie radio invalide (attendu 'radio_cable' ou 'radio_network')")
    if payload.playlist_id is not None:
        if not db.query(RadioPlaylist).filter(RadioPlaylist.id == payload.playlist_id).first():
            raise HTTPException(status_code=404, detail="Playlist radio non trouvée")
    set_radio_default_playlist_override(db, payload.channel, payload.playlist_id)
    return get_default_playlists(db)

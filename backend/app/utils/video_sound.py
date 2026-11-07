"""Réglages de son d'un canal vidéo (câblé, réseau) : mêmes réglages et mêmes bornes que ceux de la radio.

Le TRAITEMENT est fait par le lecteur (graphe Web Audio de `/kiosk` et de `/cinema`) ; le serveur valide, stocke et
diffuse ces réglages dans l'état du canal, comme le volume. Les bornes viennent de `radio_sound.py` : une seule
définition d'un réglage de son, quel que soit le canal.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.api_contract import CHANNELS, DEFAULT_CHANNEL
from app.models import Setting
from app.utils.radio_sound import default_sound, sanitize_sound

logger = logging.getLogger(__name__)


def video_sound_setting_key(channel: str) -> str:
    return f"video_sound_{channel if channel in CHANNELS else DEFAULT_CHANNEL}"


def load_video_sound(db: Session, channel: str) -> dict[str, Any]:
    """Réglages persistés d'un canal, ou réglages neutres si absents ou illisibles (jamais d'exception)."""
    row = db.query(Setting).filter(Setting.key == video_sound_setting_key(channel)).first()
    if row is None or not row.value:
        return default_sound()
    try:
        return sanitize_sound(json.loads(row.value))
    except (TypeError, ValueError):
        logger.warning("Réglage de son illisible pour le canal %s, réglages neutres utilisés", channel)
        return default_sound()


def save_video_sound(db: Session, channel: str, sound: dict[str, Any]) -> None:
    key = video_sound_setting_key(channel)
    payload = json.dumps(sanitize_sound(sound))
    row = db.query(Setting).filter(Setting.key == key).first()
    if row is not None:
        row.value = payload
    else:
        db.add(Setting(key=key, value=payload))
    db.commit()


def load_all_video_sounds_into_managers(db: Session) -> None:
    """Charge les réglages persistés dans l'état de chaque canal vidéo (au démarrage)."""
    from app.playback_manager import get_all_playback_managers

    for channel, manager in get_all_playback_managers().items():
        manager.state["sound"] = load_video_sound(db, channel)


async def apply_video_sound(db: Session, manager, raw, client_ts: float | None = None) -> dict[str, Any]:
    """Réglages de son d'UN canal : bornés (jamais d'erreur), champs absents inchangés ; persistés puis diffusés."""
    from app import config_files

    sound = sanitize_sound(raw, base=manager.state.get("sound"))
    save_video_sound(db, manager.channel, sound)
    await manager.set_sound(sound, client_ts)
    config_files.schedule_mirror()
    return sound

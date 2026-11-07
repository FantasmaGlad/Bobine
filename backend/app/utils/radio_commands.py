"""Commandes radio partagées entre la façade REST (`PUT /api/radio/sound`, `POST /api/radio/announcements/play-now`),
la commande WebSocket (`radio_set_sound`, `radio_play_announcement`) et `bobine radio` : une seule implémentation, donc
les mêmes bornes, la même persistance, les mêmes diffusions et la même copie de la configuration quel que soit le canal.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import RadioAnnouncement
from app.utils.activity_log import log_activity
from app.utils.radio_sound import sanitize_sound, save_sound


async def apply_sound(db: Session, manager, raw, client_ts: float | None = None) -> dict:
    """Réglages de son d'UNE sortie : valeurs bornées (jamais d'erreur), champs absents inchangés ; persistés, diffusés
    avec l'état du moteur, copie de la configuration demandée."""
    from app import config_files

    sound = sanitize_sound(raw, base=manager.state.get("sound"))
    save_sound(db, manager.channel, sound)
    await manager.set_sound(sound, client_ts)
    config_files.schedule_mirror()
    return sound


def resolve_announcement(db: Session, announcement_id) -> RadioAnnouncement | None:
    """Rappel actif ciblé, ou tirage aléatoire parmi les actifs si `announcement_id` est absent."""
    query = db.query(RadioAnnouncement).filter(RadioAnnouncement.enabled == True)  # noqa: E712
    if announcement_id:
        return query.filter(RadioAnnouncement.id == announcement_id).first()
    return query.order_by(func.random()).first()


async def play_announcement_now(db: Session, managers, announcement: RadioAnnouncement, client_ts: float | None = None) -> dict:
    """Déclenchement manuel, toujours en mode « duck » (fondu immédiat, la musique continue), sur chaque sortie donnée."""
    payload = {"id": announcement.id, "description": announcement.description}
    for manager in managers:
        await manager.play_announcement(payload, mode="duck", client_ts=client_ts)
    log_activity(db, "radio_announcement_played", announcement.description)
    return payload

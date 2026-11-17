"""Mixage et égaliseur de la musique de chaque sortie radio."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.api.contract import RADIO_CHANNELS
from app.radio.manager import get_all_radio_managers, get_radio_manager
from app.utils.radio_mix import sanitize_mix, save_mix
from app.utils.radio_sound import sanitize_sound, save_sound

from .base import DeviceError


def mixer_view() -> dict[str, Any]:
    return {"outputs": [
        {"channel": channel, "mix": m.state.get("mix"), "sound": m.state.get("sound"), "playing": bool(m.state.get("playing"))}
        for channel, m in get_all_radio_managers().items()
    ]}


async def apply_mixer(db: Session, channel: str, mix: dict | None, sound: dict | None) -> None:
    if channel not in RADIO_CHANNELS:
        raise DeviceError("not_found", "Sortie radio inconnue.", 404)
    manager = get_radio_manager(channel)
    if sound is not None:
        clean = sanitize_sound(sound, base=manager.state.get("sound"))
        save_sound(db, manager.channel, clean)
        await manager.set_sound(clean)
    if mix is not None:
        clean = sanitize_mix(mix, base=manager.state.get("mix"))
        save_mix(db, manager.channel, clean)
        await manager.set_mix(clean)

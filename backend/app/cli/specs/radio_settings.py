from __future__ import annotations

from app.api.contract import RADIO_CHANNELS

from .model import Spec
from .route import route

_CHANNEL = "channel=" + "|".join(RADIO_CHANNELS)

SPECS: tuple[Spec, ...] = (
    route("radio-settings", "sound", "GET", "/api/radio/sound", "réglages de son d'une sortie radio", query=(_CHANNEL,)),
    route("radio-settings", "sound-set", "PUT", "/api/radio/sound", "régler le son d'une sortie radio (JSON)",
          query=(_CHANNEL,), body=("sound:json",), pos=("sound",), raw="sound"),
    route("radio-settings", "defaults", "GET", "/api/radio/default-playlist", "ambiances par défaut des sorties"),
    route("radio-settings", "default-set", "PUT", "/api/radio/default-playlist", "choisir l'ambiance par défaut d'une sortie",
          body=(_CHANNEL, "playlist_id:int"), pos=("channel",)),
)

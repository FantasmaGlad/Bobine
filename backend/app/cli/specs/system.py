from __future__ import annotations

from app.api.contract import CHANNELS

from .model import Spec
from .route import route

_CHANNEL = "channel=" + "|".join(CHANNELS)

SPECS: tuple[Spec, ...] = (
    route("settings", "media-native", "GET", "/api/settings/media-native", "état du composant média natif"),
    route("settings", "logo", "POST", "/api/settings/logo", "importer un logo personnalisé", files=("file",)),
    route("settings", "logo-rm", "DELETE", "/api/settings/logo", "retirer le logo personnalisé", confirm="Retirer le logo personnalisé ?"),
    route("settings", "lid", "GET", "/api/settings/laptop-lid", "comportement à la fermeture du capot"),
    route("settings", "lid-set", "POST", "/api/settings/laptop-lid", "rester allumé capot fermé (on/off)",
          body=("prevent_sleep:bool",), pos=("prevent_sleep",)),
    route("settings", "storage", "GET", "/api/settings/storage", "occupation du stockage"),
    route("interrupted", "get", "GET", "/api/playback/interrupted", "lecture interrompue par un redémarrage", query=(_CHANNEL,)),
    route("interrupted", "resume", "POST", "/api/playback/interrupted/resume", "reprendre la lecture interrompue", query=(_CHANNEL,)),
    route("interrupted", "dismiss", "DELETE", "/api/playback/interrupted", "oublier la lecture interrompue", query=(_CHANNEL,)),
    route("metrics", "ratings", "GET", "/api/metrics/ratings", "notes données aux cours",
          query=("video_id:int", _CHANNEL, "limit:int")),
)

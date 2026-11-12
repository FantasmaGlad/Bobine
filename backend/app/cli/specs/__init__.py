from __future__ import annotations

from . import (
    audio, backgrounds, devices, library, logs, media, playlists, radio, radio_announcements, radio_playlists,
    radio_settings, radio_tags, schedule, storage, system, updates,
)
from .model import Arg, Call, Spec, UsageError

MODULES = (
    media, library, playlists, schedule, audio, backgrounds, radio, radio_tags, radio_playlists, radio_announcements,
    radio_settings, devices, storage, logs, system, updates,
)
SPECS: tuple[Spec, ...] = tuple(spec for module in MODULES for spec in module.SPECS)
COMMAND_HELP = {
    "media": "catalogue de tous les médias et de leurs identifiants",
    "play": "lire un média par son identifiant",
    "audio-playlists": "playlists audio du mode coach",
    "audio": "cours audio du mode coach",
    "backgrounds": "fonds animés",
    "radio-library": "morceaux de la radio",
    "radio-tags": "étiquettes de la radio",
    "radio-playlists": "playlists et ambiances de la radio",
    "radio-announcements": "annonces de la radio",
    "radio-rules": "règles de rappel des annonces",
    "radio-settings": "son et ambiance par défaut des sorties radio",
    "logs-admin": "journal d'activité et journal technique",
    "interrupted": "lecture interrompue par un redémarrage",
}

__all__ = ["Arg", "COMMAND_HELP", "Call", "SPECS", "Spec", "UsageError"]

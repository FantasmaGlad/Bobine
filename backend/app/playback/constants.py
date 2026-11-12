"""Constantes de la lecture : délais de synchronisation, battements, états."""
import enum
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


BroadcastFn = Callable[[dict], Awaitable[None]]


LOAD_LEAD_MS = 400.0


PLAY_LEAD_MS = 150.0


SEEK_LEAD_MS = 150.0


VIDEO_HEARTBEAT_SECONDS = 1.0


VIDEO_END_GRACE_SECONDS = 3.0


AUDIO_END_GRACE_SECONDS = 2.0


class PlaybackStateEnum(str, enum.Enum):
    waiting = "waiting"
    playing = "playing"
    paused = "paused"
    coach_mode = "coach_mode"
    offline = "offline"
    playlist_waiting = "playlist_waiting"
    background = "background"

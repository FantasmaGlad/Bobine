"""Gestionnaire de lecture d'un canal de diffusion, et registre des gestionnaires par canal."""
import asyncio
import logging
from typing import Any, Callable
from app.config import settings
from app.utils.playback_clock import PlaybackClock
from app.utils.radio_sound import default_sound
from app.api.contract import CHANNELS, DEFAULT_CHANNEL
from app.playback.constants import BroadcastFn, PlaybackStateEnum
from app.playback.state import StateMixin
from app.playback.broadcast import BroadcastMixin
from app.playback.video import VideoMixin
from app.playback.playlist import PlaylistMixin
from app.playback.audio import AudioMixin
from app.playback.controls import ControlsMixin

logger = logging.getLogger(__name__)


class PlaybackManager(VideoMixin, PlaylistMixin, AudioMixin, ControlsMixin, BroadcastMixin, StateMixin):
    """État de lecture global et partagé de l'écran cinéma."""

    def __init__(self, broadcast: BroadcastFn, channel: str = DEFAULT_CHANNEL):
        self._broadcast = broadcast
        self.channel = channel
        self._current_session_id: int | None = None
        self._last_session_update: float = 0.0
        self._last_direct_report = 0.0
        self._scheduled_launch_recorded = False
        self._waiting_task: asyncio.Task | None = None
        self._audio_chain_wait_task: asyncio.Task | None = None
        self._position_broadcast_task: asyncio.Task | None = None
        self._tick_seq = 0
        self._clock = PlaybackClock()
        self._audio_clock = PlaybackClock()
        self._last_heartbeat = 0.0
        self.display_counter: Callable[[str], int] = lambda channel: 0
        self._default_audio_background: dict[str, Any] | None = None
        self.state: dict[str, Any] = {
            "state": PlaybackStateEnum.waiting.value,
            "current_video": None,
            "subtitle": None,
            "position_seconds": 0.0,
            "volume": settings.volume_default,
            "sound": default_sound(),
            "speed": 1.0,
            "playlist_id": None,
            "playlist_name": None,
            "playlist_items": None,
            "playlist_index": None,
            "playlist_waiting_remaining": None,
            "current_background": None,
            "current_audio_course": None,
            "audio_tracks": None,
            "audio_track_index": None,
            "audio_playing": False,
            "audio_position_seconds": 0.0,
            "audio_chain_mode": "auto",
            "audio_chain_timer_seconds": settings.audio_chain_timer_seconds,
            "audio_chain_wait_remaining": None,
            "scheduled_launch": False,
        }


_managers: dict[str, PlaybackManager] = {}


def init_playback_managers(broadcast: BroadcastFn) -> dict[str, PlaybackManager]:
    """Crée les deux gestionnaires d'état, un par canal de diffusion."""
    global _managers
    _managers = {channel: PlaybackManager(broadcast, channel) for channel in CHANNELS}
    return _managers


def get_playback_manager(channel: str = DEFAULT_CHANNEL) -> PlaybackManager:
    manager = _managers.get(channel if channel in CHANNELS else DEFAULT_CHANNEL)
    if manager is None:
        raise RuntimeError("PlaybackManager non initialisé")
    return manager


def get_all_playback_managers() -> dict[str, PlaybackManager]:
    if not _managers:
        raise RuntimeError("PlaybackManager non initialisé")
    return _managers

"""Moteur de lecture d'une sortie radio : état, horloge, diffusion, playlist ; un moteur par sortie."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable

from app.api.contract import RADIO_CHANNELS
from app.config import settings
from app.storage.availability import media_available
from app.utils.playback_clock import PlaybackClock
from app.radio.mix import default_mix
from app.radio.sound import default_sound

from .channels import DEFAULT_RADIO_CHANNEL, normalize_radio_channel
from .constants import HEARTBEAT_SECONDS, PLAY_LEAD_MS, TRACK_END_GRACE_SECONDS, BroadcastFn
from .order import OrderMixin
from .outputs import OutputMixin
from .transport import TransportMixin

logger = logging.getLogger(__name__)


class RadioPlaybackManager(TransportMixin, OutputMixin, OrderMixin):
    def __init__(self, broadcast: BroadcastFn, channel: str = DEFAULT_RADIO_CHANNEL):
        self._broadcast = broadcast
        self.channel = normalize_radio_channel(channel)
        self._last_direct_report = 0.0
        self._clock = PlaybackClock()
        self.display_counter: Callable[[str], int] = lambda channel: 0
        self.track_end_handler: Callable[[int | None], Awaitable[None]] | None = None
        self._position_broadcast_task: asyncio.Task | None = None
        self._deferred_advance_pending = False
        self.state: dict[str, Any] = {
            "state": "idle",
            "playlist_id": None,
            "playlist_name": None,
            "order": [],
            "index": None,
            "current_track": None,
            "position_seconds": 0.0,
            "duration_seconds": None,
            "volume": settings.radio_volume_default,
            "shuffle": False,
            "repeat": "off",
            "playing": False,
            "crossfade_seconds": settings.radio_crossfade_seconds,
            "current_announcement": None,
            "tracks_since_announcement": 0,
            "sound": default_sound(),
            "mix": default_mix(),
            "route": None,
            "meter": False,
        }
        self._meter_until = 0.0

    def _lead_ms(self, nominal_ms: float) -> float:
        try:
            return nominal_ms if self.display_counter(self.channel) >= 2 else 0.0
        except Exception:
            return 0.0

    def _refresh_position(self) -> None:
        if self.state["current_track"] is None or self.state["state"] not in ("playing", "paused", "announcing"):
            return
        pos = self._clock.position()
        duration = self.state.get("duration_seconds")
        if duration:
            pos = min(pos, duration)
        self.state["position_seconds"] = pos

    def _start_clock(self, position: float = 0.0) -> None:
        self._clock.reset()
        self._clock.start(position, lead_ms=self._lead_ms(PLAY_LEAD_MS))

    def snapshot(self) -> dict:
        self._refresh_position()
        snap = dict(self.state)
        snap["channel"] = self.channel
        snap["clock"] = self._clock.to_dict()
        return snap

    async def _emit(self, cause: str, client_ts: float | None = None):
        payload: dict[str, Any] = {
            "event": "state_change",
            "cause": cause,
            "channel": self.channel,
            "data": self.snapshot(),
        }
        if client_ts is not None:
            payload["client_ts"] = client_ts
        await self._broadcast(payload)

    def start_position_broadcast_loop(self):
        if self._position_broadcast_task is None or self._position_broadcast_task.done():
            self._position_broadcast_task = asyncio.create_task(self._position_broadcast_loop())

    def stop_position_broadcast_loop(self):
        if self._position_broadcast_task and not self._position_broadcast_task.done():
            self._position_broadcast_task.cancel()
        self._position_broadcast_task = None

    async def _position_broadcast_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                await self._expire_meter()
                if self.state["playing"]:
                    if await self._end_track_if_overdue():
                        continue
                    await self._emit("radio_position_tick")
        except asyncio.CancelledError:
            pass

    async def _end_track_if_overdue(self) -> bool:
        if self.state["state"] != "playing":
            return False
        track = self.state["current_track"]
        duration = self.state.get("duration_seconds")
        if track is None or not duration or self._clock.position() < duration + TRACK_END_GRACE_SECONDS:
            return False
        logger.info("Radio : fin de piste déclenchée par l'horloge serveur")
        if self.track_end_handler is not None:
            await self.track_end_handler(track.get("id"))
        else:
            await self.track_ended(track_id=track.get("id"))
        return True

    def _sync_current(self):
        order = self.state["order"]
        idx = self.state["index"]
        if order and idx is not None and 0 <= idx < len(order):
            self.state["current_track"] = order[idx]
            self.state["duration_seconds"] = order[idx].get("duration_seconds")
        else:
            self.state["current_track"] = None
            self.state["duration_seconds"] = None

    def _advance_index(self) -> bool:
        order = self.state["order"]
        if not order:
            return False
        i = self.state["index"] or 0
        for _ in range(len(order) + 1):
            i += 1
            if i >= len(order):
                if self.state["repeat"] == "playlist":
                    if self.state["shuffle"]:
                        random.shuffle(order)
                    i = 0
                else:
                    return False
            if media_available(order[i].get("storage_id")):
                self.state["index"] = i
                return True
        return False

    async def load_playlist(self, playlist_id: int, name: str, tracks: list[dict],
                            shuffle: bool | None = None, client_ts: float | None = None,
                            repeat: str | None = None, start_paused: bool = False):
        """`repeat`, si fourni, force le mode de répétition APRÈS chargement."""
        if shuffle is not None:
            self.state["shuffle"] = bool(shuffle)
        if repeat is not None:
            self.state["repeat"] = repeat
        order = [t for t in tracks if media_available(t.get("storage_id"))]
        if self.state["shuffle"]:
            random.shuffle(order)
        self.state["playlist_id"] = playlist_id
        self.state["playlist_name"] = name
        self.state["order"] = order
        self.state["index"] = 0 if order else None
        self.state["position_seconds"] = 0.0
        playing = bool(order) and not start_paused
        self.state["playing"] = playing
        self.state["state"] = ("playing" if playing else "paused") if order else "idle"
        self.state["current_announcement"] = None
        self._deferred_advance_pending = False
        self._sync_current()
        if playing:
            self._start_clock(0.0)
        else:
            self._clock.reset()
        await self._emit("radio_load_playlist", client_ts)

    async def report_position(self, position_seconds: float):
        """Rapport de position du lecteur /radio (pas de diffusion à chaque appel — la boucle de position s'en charge)."""
        self._last_direct_report = time.monotonic()


_managers: dict[str, RadioPlaybackManager] = {}


def init_radio_managers(broadcast: BroadcastFn) -> dict[str, RadioPlaybackManager]:
    """Crée les deux moteurs radio, un par sortie."""
    global _managers
    _managers = {channel: RadioPlaybackManager(broadcast, channel) for channel in RADIO_CHANNELS}
    return _managers


def get_radio_manager(channel: str | None = None) -> RadioPlaybackManager:
    """Moteur de la sortie demandée (alias historique accepté ; défaut : réseau)."""
    manager = _managers.get(normalize_radio_channel(channel))
    if manager is None:
        raise RuntimeError("RadioPlaybackManager non initialisé")
    return manager


def get_all_radio_managers() -> dict[str, RadioPlaybackManager]:
    return dict(_managers)

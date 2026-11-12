"""Moteur de lecture du canal Radio."""
import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable

from app.config import settings
from app.storage.availability import media_available
from app.utils.playback_clock import PlaybackClock
from app.utils.radio_mix import default_mix
from app.utils.radio_sound import default_sound

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict], Awaitable[None]]

from app.api.contract import LEGACY_RADIO_CHANNEL, RADIO_CHANNELS  # noqa: E402
DEFAULT_RADIO_CHANNEL = "radio_network"


def normalize_radio_channel(value: Any) -> str:
    """Identifiant de sortie radio canonique : l'alias historique `radio` devient `radio_network` ; toute valeur absente ou inconnue retombe sur le défaut."""
    if value in RADIO_CHANNELS:
        return value
    return DEFAULT_RADIO_CHANNEL


RULE_TARGET_BOTH = "both"
RULE_TARGETS = (*RADIO_CHANNELS, RULE_TARGET_BOTH)


def normalize_rule_target(value: Any) -> str:
    """Cible d'une règle de rappel."""
    if value == RULE_TARGET_BOTH:
        return RULE_TARGET_BOTH
    return normalize_radio_channel(value)


def rule_targets_output(target: Any, radio_channel: str) -> bool:
    """Vrai si une règle de rappel de cible `target` s'applique à la sortie `radio_channel`."""
    normalized = normalize_rule_target(target)
    return normalized == RULE_TARGET_BOTH or normalized == normalize_radio_channel(radio_channel)


def is_radio_channel(value: Any) -> bool:
    """Vrai pour un identifiant de sortie radio, alias historique compris."""
    return value == LEGACY_RADIO_CHANNEL or value in RADIO_CHANNELS

REPEAT_MODES = ("off", "playlist", "track")

HEARTBEAT_SECONDS = 1.0
TRACK_END_GRACE_SECONDS = 2.0
PLAY_LEAD_MS = 150.0
METER_LEASE_SECONDS = 12.0


class RadioPlaybackManager:
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

    async def play(self, client_ts: float | None = None):
        if self.state["current_track"] is None:
            return
        self.state["playing"] = True
        self.state["state"] = "playing"
        if not self._clock.running:
            self._clock.start(lead_ms=self._lead_ms(PLAY_LEAD_MS))
        await self._emit("radio_play", client_ts)

    async def pause(self, client_ts: float | None = None):
        if self.state["current_track"] is None:
            return
        self._clock.pause()
        self.state["playing"] = False
        self.state["state"] = "paused"
        await self._emit("radio_pause", client_ts)

    async def stop(self, client_ts: float | None = None):
        self.state.update({
            "state": "idle", "playlist_id": None, "playlist_name": None,
            "order": [], "index": None, "current_track": None,
            "duration_seconds": None, "position_seconds": 0.0, "playing": False,
            "current_announcement": None,
        })
        self._deferred_advance_pending = False
        self._clock.reset()
        await self._emit("radio_stop", client_ts)

    async def next_track(self, client_ts: float | None = None):
        """Passage manuel : boucle en fin de liste même sans répétition (geste volontaire du DJ), contrairement à la fin de piste automatique."""
        if not self.state["order"]:
            return
        if not self._advance_index():
            self.state["index"] = 0
            if self.state["shuffle"]:
                random.shuffle(self.state["order"])
        self.state["position_seconds"] = 0.0
        self.state["playing"] = True
        self.state["state"] = "playing"
        self._sync_current()
        self._start_clock(0.0)
        await self._emit("radio_next_track", client_ts)

    async def previous_track(self, client_ts: float | None = None):
        if not self.state["order"]:
            return
        self._refresh_position()
        if self.state["position_seconds"] > 3.0:
            self.state["position_seconds"] = 0.0
            self._start_clock(0.0)
            await self._emit("radio_restart_track", client_ts)
            return
        i = (self.state["index"] or 0) - 1
        if i < 0:
            i = len(self.state["order"]) - 1 if self.state["repeat"] == "playlist" else 0
        self.state["index"] = i
        self.state["position_seconds"] = 0.0
        self.state["playing"] = True
        self.state["state"] = "playing"
        self._sync_current()
        self._start_clock(0.0)
        await self._emit("radio_previous_track", client_ts)

    async def jump_to(self, index: int, client_ts: float | None = None):
        order = self.state["order"]
        if not order or not (0 <= index < len(order)):
            return
        self.state["index"] = index
        self.state["position_seconds"] = 0.0
        self.state["playing"] = True
        self.state["state"] = "playing"
        self._sync_current()
        self._start_clock(0.0)
        await self._emit("radio_jump_to_track", client_ts)

    async def _advance_or_stop(self, client_ts: float | None = None):
        if self._advance_index():
            self.state["position_seconds"] = 0.0
            self.state["playing"] = True
            self.state["state"] = "playing"
            self._sync_current()
            self._start_clock(0.0)
            await self._emit("radio_next_track", client_ts)
        else:
            self.state["playing"] = False
            self.state["state"] = "paused"
            self.state["position_seconds"] = 0.0
            self._clock.reset()
            await self._emit("radio_ended", client_ts)

    async def track_ended(self, client_ts: float | None = None, track_id: int | None = None):
        """Fin de piste rapportée par un lecteur /radio : enchaînement auto."""
        if not self.state["order"]:
            return
        current = self.state["current_track"]
        if track_id is not None and current is not None and current.get("id") != track_id:
            return
        if self.state["repeat"] == "track":
            self.state["position_seconds"] = 0.0
            self._start_clock(0.0)
            await self._emit("radio_restart_track", client_ts)
            return
        await self._advance_or_stop(client_ts)

    async def play_announcement(
        self, announcement: dict, mode: str, client_ts: float | None = None, deferred_advance: bool = False,
    ):
        """Déclenche un rappel."""
        self.state["current_announcement"] = {
            "id": announcement["id"], "description": announcement["description"], "mode": mode,
        }
        self.state["tracks_since_announcement"] = 0
        self._deferred_advance_pending = deferred_advance
        self.state["state"] = "announcing"
        await self._emit("radio_play_announcement", client_ts)

    async def announcement_ended(self, client_ts: float | None = None):
        """Fin de rappel rapportée par le lecteur /radio."""
        self.state["current_announcement"] = None
        if self._deferred_advance_pending:
            self._deferred_advance_pending = False
            await self._advance_or_stop(client_ts)
        else:
            self.state["state"] = "playing" if self.state["playing"] else "paused"
            await self._emit("radio_announcement_ended", client_ts)

    async def seek(self, position_seconds: float, client_ts: float | None = None):
        self.state["position_seconds"] = max(0.0, position_seconds)
        if self.state["current_track"] is not None:
            self._clock.seek(self.state["position_seconds"], lead_ms=self._lead_ms(PLAY_LEAD_MS) if self._clock.running else 0.0)
        await self._emit("radio_seek", client_ts)

    async def set_volume(self, volume: float, client_ts: float | None = None):
        self.state["volume"] = max(0, min(100, int(volume)))
        await self._emit("radio_volume", client_ts)

    async def set_sound(self, sound: dict, client_ts: float | None = None):
        """Applique des réglages de son DÉJÀ validés."""
        self.state["sound"] = sound
        await self._emit("radio_sound_change", client_ts)

    async def set_mix(self, mix: dict, client_ts: float | None = None):
        """Applique une table de mixage DÉJÀ validée."""
        self.state["mix"] = mix
        await self._emit("radio_mix_change", client_ts)

    async def set_route(self, route: dict | None) -> None:
        """Publie la route audio de la sortie (devices/routing.py) ; sans effet, ni diffusion, si elle n'a pas changé."""
        if self.state.get("route") == route:
            return
        self.state["route"] = route
        await self._emit("radio_route_change")

    async def request_meter(self) -> None:
        """Une interface de mixage est ouverte : le lecteur doit mesurer ses niveaux pendant `METER_LEASE_SECONDS`."""
        self._meter_until = time.monotonic() + METER_LEASE_SECONDS
        if not self.state.get("meter"):
            self.state["meter"] = True
            await self._emit("radio_meter")

    async def _expire_meter(self) -> None:
        if self.state.get("meter") and time.monotonic() >= self._meter_until:
            self.state["meter"] = False
            await self._emit("radio_meter")

    async def relay_levels(self, levels: dict[str, int]) -> None:
        """Relaie les niveaux mesurés par le lecteur aux interfaces abonnées à cette sortie (évènement léger, sans état)."""
        if levels and self.state.get("meter"):
            await self._broadcast({"event": "radio_levels", "channel": self.channel, "levels": levels})

    async def set_shuffle(self, on: bool, client_ts: float | None = None):
        self.state["shuffle"] = bool(on)
        order = self.state["order"]
        idx = self.state["index"]
        if on and order and idx is not None and idx + 1 < len(order):
            upcoming = order[idx + 1:]
            random.shuffle(upcoming)
            self.state["order"] = order[: idx + 1] + upcoming
        await self._emit("radio_set_shuffle", client_ts)

    async def set_repeat(self, mode: str, client_ts: float | None = None):
        if mode not in REPEAT_MODES:
            return
        self.state["repeat"] = mode
        await self._emit("radio_set_repeat", client_ts)

    async def add_to_queue(self, track: dict, client_ts: float | None = None):
        """Ajoute une piste en FIN de file d'attente."""
        order = self.state["order"]
        order.append(track)
        self.state["order"] = order
        if self.state["index"] is None:
            self.state["index"] = len(order) - 1
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def play_next(self, track: dict, client_ts: float | None = None):
        """« Lire ensuite » : insère une piste juste après la piste courante, devant tout ce qui est déjà en file d'attente."""
        order = self.state["order"]
        idx = self.state["index"]
        insert_at = (idx + 1) if idx is not None else len(order)
        order.insert(insert_at, track)
        self.state["order"] = order
        if self.state["index"] is None:
            self.state["index"] = insert_at
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def move_in_order(self, from_index: int, to_index: int, client_ts: float | None = None):
        """Déplace une piste de la file « À suivre » (glisser-déposer de l'admin)."""
        order = self.state["order"]
        cur = self.state["index"]
        if cur is None or not order:
            return
        first = cur + 1
        if not (first <= from_index < len(order)):
            return
        target = max(first, min(to_index, len(order) - 1))
        if target == from_index:
            return
        order.insert(target, order.pop(from_index))
        self.state["order"] = order
        await self._emit("radio_queue_changed", client_ts)

    async def remove_from_order(self, index: int, client_ts: float | None = None):
        """Retire une piste de l'ordre de lecture (file d'attente)."""
        order = self.state["order"]
        if not (0 <= index < len(order)):
            return
        cur = self.state["index"] or 0
        order.pop(index)
        if index < cur:
            self.state["index"] = cur - 1
        elif index == cur:
            self.state["index"] = min(cur, len(order) - 1) if order else None
        self.state["order"] = order
        if not order:
            self.state.update({"playing": False, "state": "idle"})
            self._clock.reset()
        self._sync_current()
        if index == cur and order:
            self.state["position_seconds"] = 0.0
            if self.state["playing"]:
                self._start_clock(0.0)
            else:
                self._clock.reset()
        await self._emit("radio_queue_changed", client_ts)

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

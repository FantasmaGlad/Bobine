"""État logique partagé : position, instantané, diffusion aux écrans."""
import logging
from typing import Any
from app.playback.constants import PlaybackStateEnum

logger = logging.getLogger(__name__)


class StateMixin:
    def _lead_ms(self, nominal_ms: float) -> float:
        """Délai de démarrage synchronisé : `nominal_ms` s'il y a au moins deux
        écrans de diffusion sur le canal à caler entre eux, sinon 0 (réponse
        immédiate). Ne lève jamais : en cas de doute, aucun délai."""
        try:
            return nominal_ms if self.display_counter(self.channel) >= 2 else 0.0
        except Exception:
            return 0.0

    def _track_duration(self) -> float | None:
        tracks = self.state.get("audio_tracks") or []
        idx = self.state.get("audio_track_index")
        if idx is not None and 0 <= idx < len(tracks):
            return tracks[idx].get("duration_seconds")
        return None

    def _refresh_audio_position(self) -> None:
        if self.state.get("current_audio_course") is None:
            return
        pos = self._audio_clock.position()
        duration = self._track_duration()
        if duration:
            pos = min(pos, duration)
        self.state["audio_position_seconds"] = pos

    def _refresh_position(self) -> None:
        """Aligne `state["position_seconds"]` (champ historique lu par l'API REST,
        le planning de reprise et les clients non migrés) sur l'horloge."""
        self._refresh_audio_position()
        current = self.state.get("current_video")
        if current is None:
            return
        if self.state["state"] not in (
            PlaybackStateEnum.playing.value,
            PlaybackStateEnum.paused.value,
        ):
            return
        pos = self._clock.position()
        duration = current.get("duration_seconds")
        if duration:
            pos = min(pos, duration)
        self.state["position_seconds"] = pos

    def snapshot(self) -> dict:
        self._refresh_position()
        snap = dict(self.state)
        # Ancre de l'horloge (cf. playback_clock.PlaybackClock.to_dict) : les
        # écrans en déduisent la position à tout instant, sans tick.
        snap["clock"] = self._clock.to_dict()
        snap["audio_clock"] = self._audio_clock.to_dict()
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
        if cause == "position_tick":
            self._tick_seq += 1
            payload["tick_seq"] = self._tick_seq
        await self._broadcast(payload)

    def _cancel_waiting(self):
        if self._waiting_task and not self._waiting_task.done():
            self._waiting_task.cancel()
        self._waiting_task = None

    def _cancel_audio_chain_wait(self):
        if self._audio_chain_wait_task and not self._audio_chain_wait_task.done():
            self._audio_chain_wait_task.cancel()
        self._audio_chain_wait_task = None

    def _clear_audio_coach(self):
        """Sort du mode audio coach — appelé par tout ce qui
        prend le relais sur l'écran (cours vidéo, playlist, fond animé,
        arrêt manuel). Ne s'applique PAS à la règle de priorité du mode coach, qui
        empêche au contraire une programmation automatique d'appeler ceci."""
        self._cancel_audio_chain_wait()
        self.state["current_audio_course"] = None
        self.state["audio_tracks"] = None
        self.state["audio_track_index"] = None
        self.state["audio_playing"] = False
        self.state["audio_position_seconds"] = 0.0
        self.state["audio_chain_wait_remaining"] = None
        self._audio_clock.reset()
        self._default_audio_background = None

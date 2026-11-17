"""Commandes de transport du moteur radio : lecture, pause, pistes, position."""

from __future__ import annotations

import random

from .constants import PLAY_LEAD_MS


class TransportMixin:
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

    async def seek(self, position_seconds: float, client_ts: float | None = None):
        self.state["position_seconds"] = max(0.0, position_seconds)
        if self.state["current_track"] is not None:
            self._clock.seek(self.state["position_seconds"], lead_ms=self._lead_ms(PLAY_LEAD_MS) if self._clock.running else 0.0)
        await self._emit("radio_seek", client_ts)


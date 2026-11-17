"""Sortie du moteur radio : annonces, volume, son, mixage, routage et vumètre."""

from __future__ import annotations

import time

from .constants import METER_LEASE_SECONDS


class OutputMixin:
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


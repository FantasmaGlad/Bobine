"""Réglages de lecture : volume, son, sous-titres, vitesse."""
import logging

logger = logging.getLogger(__name__)


class ControlsMixin:
    async def set_volume(self, volume: float, client_ts: float | None = None):
        self.state["volume"] = max(0, min(100, int(volume)))
        await self._emit("volume", client_ts)

    async def set_sound(self, sound: dict, client_ts: float | None = None):
        """Applique des réglages de son DÉJÀ validés (utils/video_sound.py) et les diffuse ; persistance par l'appelant."""
        self.state["sound"] = sound
        await self._emit("sound_change", client_ts)

    async def set_subtitle(self, subtitle: int | str | None, client_ts: float | None = None):
        """Choix des sous-titres affichés par les kiosques du canal."""
        if subtitle in ("off", None):
            self.state["subtitle"] = subtitle
        else:
            try:
                self.state["subtitle"] = int(subtitle)
            except (TypeError, ValueError):
                return
        await self._emit("subtitle", client_ts)

    async def set_speed(self, speed: float, client_ts: float | None = None):
        self.state["speed"] = max(0.25, min(2.0, float(speed)))
        self._clock.set_rate(self.state["speed"])
        await self._emit("speed", client_ts)

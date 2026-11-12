"""Diffusion périodique de la position et fin d'un média que l'écran n'a pas signalée."""
import asyncio
import logging
import time
from app.playback.constants import AUDIO_END_GRACE_SECONDS, PlaybackStateEnum, VIDEO_END_GRACE_SECONDS, VIDEO_HEARTBEAT_SECONDS

logger = logging.getLogger(__name__)


class BroadcastMixin:
    def start_position_broadcast_loop(self):
        """À appeler une fois au démarrage du worker (lifespan FastAPI).
        Diffuse la position à intervalle fixe pendant la lecture,
        plutôt qu'à chaque rapport silencieux du kiosk (cf. report_position)."""
        if self._position_broadcast_task is None or self._position_broadcast_task.done():
            self._position_broadcast_task = asyncio.create_task(self._position_broadcast_loop())

    def stop_position_broadcast_loop(self):
        if self._position_broadcast_task and not self._position_broadcast_task.done():
            self._position_broadcast_task.cancel()
        self._position_broadcast_task = None

    async def _position_broadcast_loop(self):
        try:
            while True:
                await asyncio.sleep(0.25)
                now = time.monotonic()

                is_video_playing = self.state["state"] == PlaybackStateEnum.playing.value
                is_audio_playing = (
                    self.state["state"] == PlaybackStateEnum.coach_mode.value and self.state["audio_playing"]
                )
                if is_video_playing:
                    # Vidéo : l'horloge serveur avance seule, qu'un kiosque
                    # rapporte ou non — heartbeat lent, pas de tick à 4 Hz.
                    if now - self._last_heartbeat >= VIDEO_HEARTBEAT_SECONDS:
                        self._last_heartbeat = now
                        if await self._end_video_if_overdue():
                            continue
                        await self._emit("position_tick")
                elif is_audio_playing:
                    # Audio coach : l'horloge serveur avance seule ;
                    # heartbeat lent (la minuterie du coach s'interpole
                    # localement) et fin de piste enchaînée par le serveur si
                    # aucun écran ne la signale.
                    if now - self._last_heartbeat >= VIDEO_HEARTBEAT_SECONDS:
                        self._last_heartbeat = now
                        if await self._end_audio_track_if_overdue():
                            continue
                        await self._emit("position_tick")
        except asyncio.CancelledError:
            pass

    async def _end_video_if_overdue(self) -> bool:
        """Filet de sécurité : si la position dépasse la durée connue d'une
        marge, termine le cours côté serveur (un écran peut être absent,
        bloqué en mise en mémoire tampon ou ne jamais envoyer `video_ended`).
        Retourne True si la fin a été déclenchée."""
        current = self.state.get("current_video")
        duration = (current or {}).get("duration_seconds")
        if not duration or self._clock.position() < duration + VIDEO_END_GRACE_SECONDS:
            return False
        logger.info(f"Canal {self.channel} : fin de cours déclenchée par l'horloge serveur")
        await self.video_ended(video_id=current["id"])
        return True

    async def _end_audio_track_if_overdue(self) -> bool:
        duration = self._track_duration()
        if not duration or self._audio_clock.position() < duration + AUDIO_END_GRACE_SECONDS:
            return False
        logger.info(f"Canal {self.channel} : fin de piste déclenchée par l'horloge serveur")
        await self.audio_track_ended(track_index=self.state.get("audio_track_index"))
        return True

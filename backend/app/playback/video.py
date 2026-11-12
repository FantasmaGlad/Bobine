"""Lecture d'une vidéo : chargement, commandes, fin, position rapportée par l'écran."""
import asyncio
import logging
import time
from app.config import settings
from app.playback.constants import LOAD_LEAD_MS, PLAY_LEAD_MS, PlaybackStateEnum, SEEK_LEAD_MS
from app.playback.sessions import _db_close_scheduled_launch, _db_close_session, _db_start_session, _db_update_session

logger = logging.getLogger(__name__)


class VideoMixin:
    async def load(
        self,
        video_id: int,
        title: str,
        duration_seconds: float | None,
        program: str | None = None,
        client_ts: float | None = None,
        keep_playlist: bool = False,
        thumbnail_url: str | None = None,
        release: str | None = None,
        description: str | None = None,
        audio_channels: int | None = None,
        audio_codec: str | None = None,
        fps: float | None = None,
        bitrate_kbps: int | None = None,
        width: int | None = None,
        height: int | None = None,
        launch_type: str = "kiosk",
        scheduled: bool = False,
        start_position: float = 0.0,
    ):
        """
        Lance un cours directement en lecture, à `start_position` (reprise d'une programmation interrompue).
        """
        if not scheduled:
            await self._close_scheduled_launch()
        # Clôture de la session précédente si elle était encore ouverte
        if self._current_session_id is not None:
            old_sess_id = self._current_session_id
            self._current_session_id = None
            pos = self.state.get("position_seconds", 0.0)
            asyncio.create_task(asyncio.to_thread(_db_close_session, old_sess_id, pos))

        self.state["current_background"] = None
        self._clear_audio_coach()
        if not keep_playlist:
            self._cancel_waiting()
            self.state["playlist_id"] = None
            self.state["playlist_name"] = None
            self.state["playlist_items"] = None
            self.state["playlist_index"] = None
            self.state["playlist_waiting_remaining"] = None

        self.state["subtitle"] = None
        self.state["current_video"] = {
            "id": video_id,
            "title": title,
            "duration_seconds": duration_seconds,
            "program": program,
            "release": release,
            "thumbnail_url": thumbnail_url,
            "description": description,
            "audio_channels": audio_channels,
            "audio_codec": audio_codec,
            "fps": fps,
            "bitrate_kbps": bitrate_kbps,
            "width": width,
            "height": height,
        }
        self.state["position_seconds"] = start_position
        self.state["volume"] = self.state.get("volume", settings.volume_default)
        self.state["state"] = PlaybackStateEnum.playing.value
        self.state["scheduled_launch"] = scheduled
        self._clock.reset()
        self._clock.set_rate(self.state["speed"])
        self._clock.start(start_position, lead_ms=self._lead_ms(LOAD_LEAD_MS))
        self._last_heartbeat = time.monotonic()

        # Démarrage de la session SQLite d'assiduité
        self._current_session_id = await asyncio.to_thread(
            _db_start_session, video_id, self.channel, launch_type, duration_seconds or 0.0
        )
        self._last_session_update = time.monotonic()

        await self._emit("load", client_ts)

    def note_scheduled_launch_recorded(self) -> None:
        """Le planificateur vient d'enregistrer ce lancement en base : il faudra le clore quand il quittera l'écran."""
        self._scheduled_launch_recorded = True

    async def _close_scheduled_launch(self) -> None:
        if not self._scheduled_launch_recorded:
            return
        self._scheduled_launch_recorded = False
        await asyncio.to_thread(_db_close_scheduled_launch, self.channel)

    async def video_ended(self, client_ts: float | None = None, video_id: int | None = None):
        """Gère la fin naturelle d'une vidéo signalée par un écran.

        Idempotent : TOUS les écrans du canal (miroirs compris) envoient
        `video_ended` à la fin du cours, et le serveur peut déjà l'avoir
        déclenchée lui-même (horloge). Sans cette garde, le signal tardif d'un
        second écran terminait le cours SUIVANT dès son démarrage. `video_id`
        (celui que l'écran vient de finir) doit donc être le cours en lecture ;
        s'il est absent (client ancien), seul l'état « en lecture » est exigé.
        """
        current = self.state.get("current_video")
        if current is None or self.state["state"] != PlaybackStateEnum.playing.value:
            return
        if video_id is not None and current.get("id") != video_id:
            return
        self._cancel_waiting()
        duration = current.get("duration_seconds")
        self._clock.pause()
        if duration:
            self._clock.seek(duration)

        # Clôture avec complétion validée de la session de lecture
        if self._current_session_id is not None:
            sess_id = self._current_session_id
            self._current_session_id = None
            total_dur = (self.state.get("current_video") or {}).get("duration_seconds") or self.state.get("position_seconds", 0.0)
            asyncio.create_task(asyncio.to_thread(_db_close_session, sess_id, total_dur, True))

        idx = self.state["playlist_index"]
        items = self.state["playlist_items"]
        if idx is not None and items is not None:
            if idx + 1 < len(items):
                # Transition vers l'écran d'attente intercalée
                self.state["state"] = PlaybackStateEnum.playlist_waiting.value
                self.state["playlist_waiting_remaining"] = float(settings.wait_time_between_courses)
                self._waiting_task = asyncio.create_task(self._run_waiting_period())
                await self._emit("video_ended", client_ts)
            else:
                # Fin de la playlist
                await self.stop(client_ts)
        else:
            # Pas de playlist active, comportement stop standard
            await self.stop(client_ts)

    async def play(self, client_ts: float | None = None):
        # En mode coach, "Lecture" pilote la piste audio en cours
        # plutôt que la vidéo — même bouton, comportement contextuel (un seul état partagé, pas de mode de contrôle séparé par écran).
        if self.state["current_audio_course"] is not None:
            self.state["audio_playing"] = True
            if not self._audio_clock.running:
                self._audio_clock.start(lead_ms=self._lead_ms(PLAY_LEAD_MS))
            self._last_heartbeat = time.monotonic()
            await self._emit("play", client_ts)
            return
        if (
            self.state["current_video"] is None
            or self.state["state"] == PlaybackStateEnum.playlist_waiting.value
        ):
            return
        self.state["state"] = PlaybackStateEnum.playing.value
        if not self._clock.running:
            self._clock.start(lead_ms=self._lead_ms(PLAY_LEAD_MS))
        self._last_heartbeat = time.monotonic()
        await self._emit("play", client_ts)

    async def pause(self, client_ts: float | None = None):
        if self.state["current_audio_course"] is not None:
            self.state["audio_playing"] = False
            self._audio_clock.pause()
            await self._emit("pause", client_ts)
            return
        if (
            self.state["current_video"] is None
            or self.state["state"] == PlaybackStateEnum.playlist_waiting.value
        ):
            return
        self._clock.pause()
        self.state["state"] = PlaybackStateEnum.paused.value
        await self._emit("pause", client_ts)

    async def stop(self, client_ts: float | None = None):
        self._cancel_waiting()
        self._clear_audio_coach()
        await self._close_scheduled_launch()

        # Clôture de la session d'assiduité avec position finale
        if self._current_session_id is not None:
            sess_id = self._current_session_id
            self._current_session_id = None
            pos = self.state.get("position_seconds", 0.0)
            asyncio.create_task(asyncio.to_thread(_db_close_session, sess_id, pos))

        self.state["state"] = PlaybackStateEnum.waiting.value
        self.state["current_video"] = None
        self.state["position_seconds"] = 0.0
        self._clock.reset()
        self.state["playlist_id"] = None
        self.state["playlist_name"] = None
        self.state["playlist_items"] = None
        self.state["playlist_index"] = None
        self.state["playlist_waiting_remaining"] = None
        self.state["current_background"] = None
        await self._emit("stop", client_ts)

    async def seek(self, position_seconds: float, client_ts: float | None = None):
        if self.state["current_video"] is None or self.state["state"] == PlaybackStateEnum.playlist_waiting.value:
            return
        duration = self.state["current_video"].get("duration_seconds")
        position_seconds = max(0.0, position_seconds)
        if duration:
            position_seconds = min(position_seconds, duration)
        self.state["position_seconds"] = position_seconds
        self._clock.seek(position_seconds, lead_ms=self._lead_ms(SEEK_LEAD_MS) if self._clock.running else 0.0)
        self._last_heartbeat = time.monotonic()
        await self._emit("seek", client_ts)

    async def report_position(self, position_seconds: float):
        """
        Rapport de la position réelle d'un écran (kiosque primaire).

        La position est portée par l'horloge serveur
        (`PlaybackClock`) : ce rapport N'EST PLUS la source de la position et
        ne la modifie plus (il en fixait l'âge et la précision, et sans écran
        primaire connecté le cours n'avançait pas). Il sert uniquement à :
          * mémoriser qu'un écran joue réellement (`_last_direct_report`,
            diagnostic) ;
          * alimenter le suivi d'assiduité en base.
        Silencieux : aucune diffusion (cf. `_position_broadcast_loop`).
        """
        if self.state["current_video"] is None or self.state["state"] == PlaybackStateEnum.playlist_waiting.value:
            return
        now_mono = time.monotonic()
        self._last_direct_report = now_mono

        # Throttling de la mise à jour en base toutes les 5s
        if self._current_session_id is not None and (now_mono - self._last_session_update >= 5.0):
            self._last_session_update = now_mono
            asyncio.create_task(
                asyncio.to_thread(_db_update_session, self._current_session_id, min(position_seconds, self._clock.position() + 5.0))
            )

    async def load_background(self, background_id: int, title: str, is_image: bool = False, client_ts: float | None = None):
        """Lance un fond animé en boucle infinie, plein écran, sans son. Prend le relais immédiatement sur toute lecture en cours — pas
        de compte à rebours, une boucle d'ambiance n'est pas un « lancement de
        cours » (la règle ne s'applique qu'aux vidéos de cours). `is_image` : le kiosk rend une <img> figée
        plutôt qu'une <video> en boucle quand ce fond est une image fixe."""
        self._cancel_waiting()
        self._clear_audio_coach()
        await self._close_scheduled_launch()
        self.state["state"] = PlaybackStateEnum.background.value
        self.state["current_video"] = None
        self.state["position_seconds"] = 0.0
        self._clock.reset()
        self.state["playlist_id"] = None
        self.state["playlist_name"] = None
        self.state["playlist_items"] = None
        self.state["playlist_index"] = None
        self.state["playlist_waiting_remaining"] = None
        self.state["current_background"] = {"id": background_id, "title": title, "is_image": is_image}
        await self._emit("load_background", client_ts)

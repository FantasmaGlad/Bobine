"""Cours audio et playlists audio : pistes, fond, enchaînement."""
import asyncio
import logging
import time
from app.playback.constants import PLAY_LEAD_MS, PlaybackStateEnum

logger = logging.getLogger(__name__)


class AudioMixin:
    # ------------------------------------------------------------------
    # Mode audio coach
    # ------------------------------------------------------------------
    async def load_audio_course(
        self,
        course_id: int,
        title: str,
        program: str | None,
        background_id: int | None,
        tracks: list[dict],
        chain_mode: str | None = None,
        chain_timer_seconds: float | None = None,
        client_ts: float | None = None,
        background_title: str | None = None,
        background_is_image: bool = False,
    ):
        """Lance un cours audio : bascule immédiate en mode coach, lecture de
        la première piste.
        `current_background` est peuplé au même format que load_background() : le kiosk n'a plus
        qu'UNE seule source de vérité pour rendre le fond, qu'on soit en mode
        "background" pur ou en mode coach avec fond d'ambiance."""
        self._cancel_waiting()
        await self._close_scheduled_launch()
        self._cancel_audio_chain_wait()
        self.state["current_video"] = None
        self.state["position_seconds"] = 0.0
        self.state["playlist_id"] = None
        self.state["playlist_name"] = None
        self.state["playlist_items"] = None
        self.state["playlist_index"] = None
        self.state["playlist_waiting_remaining"] = None
        self._default_audio_background = (
            {"id": background_id, "title": background_title or "", "is_image": background_is_image}
            if background_id
            else None
        )

        self.state["state"] = PlaybackStateEnum.coach_mode.value
        self.state["current_audio_course"] = {
            "id": course_id,
            "title": title,
            "program": program,
            "background_id": background_id,
        }
        self.state["audio_tracks"] = tracks
        self.state["audio_track_index"] = 0 if tracks else None
        self.state["audio_playing"] = False
        self.state["audio_position_seconds"] = 0.0
        self._audio_clock.reset()
        # Fond RÉELLEMENT affiché pour la première piste : peut différer du fond
        # de repli ci-dessus si CETTE piste a son propre fond.
        self.state["current_background"] = self._track_background(tracks[0]) if tracks else None
        if chain_mode in ("auto", "manual"):
            self.state["audio_chain_mode"] = chain_mode
        if chain_timer_seconds is not None:
            self.state["audio_chain_timer_seconds"] = max(1, int(chain_timer_seconds))
        await self._emit("load_audio_course", client_ts)

    async def load_audio_playlist(
        self,
        playlist_id: int,
        playlist_name: str,
        tracks: list[dict],
        chain_mode: str | None = None,
        chain_timer_seconds: float | None = None,
        client_ts: float | None = None,
    ):
        """Lance une playlist audio ("édition mixée") : une playlist est une séquence de PISTES
        individuelles, possiblement issues de plusieurs cours/programmes
        différents — traitée en mode coach exactement comme un cours normal
        dont les pistes auraient été choisies une par une, sans notion de
        "cours suivant" à enchaîner (`tracks` est déjà la liste à plat)."""
        if not tracks:
            await self.stop(client_ts)
            return
        await self.load_audio_course(
            playlist_id, playlist_name, None, None, tracks,
            chain_mode=chain_mode, chain_timer_seconds=chain_timer_seconds, client_ts=client_ts,
        )

    def _track_background(self, track: dict) -> dict | None:
        """Fond à afficher pour CETTE piste : le sien propre s'il en a un, sinon le fond
        de repli du cours/playlist (celui choisi au lancement, éventuellement
        aucun)."""
        background_id = track.get("background_id")
        if background_id:
            return {
                "id": background_id,
                "title": track.get("background_title") or "",
                "is_image": bool(track.get("background_is_image")),
            }
        return self._default_audio_background

    def _goto_track(self, index: int, client_ts: float | None = None) -> bool:
        tracks = self.state["audio_tracks"]
        if not tracks or index < 0 or index >= len(tracks):
            return False
        self._cancel_audio_chain_wait()
        self.state["audio_track_index"] = index
        self.state["audio_position_seconds"] = 0.0
        self.state["audio_playing"] = True
        self._audio_clock.reset()
        self._audio_clock.start(0.0, lead_ms=self._lead_ms(PLAY_LEAD_MS))
        self._last_heartbeat = time.monotonic()
        self.state["current_background"] = self._track_background(tracks[index])
        return True

    async def audio_next_track(self, client_ts: float | None = None):
        idx = self.state["audio_track_index"]
        if idx is None:
            return
        if self._goto_track(idx + 1, client_ts):
            await self._emit("audio_next_track", client_ts)
        else:
            # Dernière piste déjà atteinte : fin du cours, on reste affiché
            # mais en pause.
            self._cancel_audio_chain_wait()
            self.state["audio_playing"] = False
            self._audio_clock.pause()
            await self._emit("audio_course_ended", client_ts)

    async def audio_previous_track(self, client_ts: float | None = None):
        idx = self.state["audio_track_index"]
        if idx is None:
            return
        if self._goto_track(idx - 1, client_ts):
            await self._emit("audio_previous_track", client_ts)

    async def audio_restart_track(self, client_ts: float | None = None):
        """Relance la piste en cours depuis le début."""
        if self.state["audio_track_index"] is None:
            return
        self._cancel_audio_chain_wait()
        self.state["audio_position_seconds"] = 0.0
        self.state["audio_playing"] = True
        self._audio_clock.reset()
        self._audio_clock.start(0.0, lead_ms=self._lead_ms(PLAY_LEAD_MS))
        self._last_heartbeat = time.monotonic()
        await self._emit("audio_restart_track", client_ts)

    async def audio_jump_to_track(self, index: int, client_ts: float | None = None):
        """Saut direct à une piste depuis la liste (bottom sheet)."""
        if self._goto_track(index, client_ts):
            await self._emit("audio_jump_to_track", client_ts)

    async def audio_set_background(
        self,
        background_id: int | None,
        title: str | None,
        is_image: bool,
        client_ts: float | None = None,
    ):
        """Change (ou retire) le fond d'ambiance du mode coach EN COURS de
        lecture — sans ça, le fond n'était fixé qu'au
        lancement du cours (via l'attribut background_id persistant du
        cours), impossible à changer une fois la lecture démarrée."""
        if self.state["current_audio_course"] is None:
            return
        self.state["current_audio_course"]["background_id"] = background_id
        self.state["current_background"] = (
            {"id": background_id, "title": title or "", "is_image": is_image} if background_id else None
        )
        await self._emit("audio_set_background", client_ts)

    async def audio_set_chain_mode(self, mode: str, client_ts: float | None = None):
        if mode not in ("auto", "manual"):
            return
        self._cancel_audio_chain_wait()
        self.state["audio_chain_mode"] = mode
        self.state["audio_chain_wait_remaining"] = None
        await self._emit("audio_chain_mode", client_ts)

    async def audio_set_chain_timer(self, seconds: float, client_ts: float | None = None):
        self.state["audio_chain_timer_seconds"] = max(1, int(seconds))
        await self._emit("audio_chain_timer", client_ts)

    async def audio_report_position(self, position_seconds: float):
        """Même logique silencieuse que report_position,
        côté piste audio."""
        if self.state["current_audio_course"] is None:
            return
        # La position audio vient de l'horloge serveur ; ce rapport
        # ne la modifie plus (il en fixait l'âge et la précision).
        self._last_direct_report = time.monotonic()

    async def _run_audio_chain_wait(self):
        try:
            remaining = self.state["audio_chain_wait_remaining"] or 0.0
            while remaining > 0:
                await asyncio.sleep(1.0)
                remaining -= 1.0
                self.state["audio_chain_wait_remaining"] = max(0.0, remaining)
                await self._emit("audio_chain_wait_tick")
            # Détache CE task AVANT d'enchaîner (même correctif que
            # _run_waiting_period) : _goto_track() appelle
            # _cancel_audio_chain_wait(), qui annulerait sinon le task courant
            # et interromprait le broadcast "audio_next_track" ci-dessous.
            self._audio_chain_wait_task = None
            self.state["audio_chain_wait_remaining"] = None
            idx = self.state["audio_track_index"]
            if idx is not None and self._goto_track(idx + 1):
                await self._emit("audio_next_track")
            else:
                self.state["audio_playing"] = False
                self._audio_clock.pause()
                await self._emit("audio_course_ended")
        except asyncio.CancelledError:
            pass

    async def audio_track_ended(self, client_ts: float | None = None, track_index: int | None = None):
        """
        Fin naturelle d'une piste signalée par le kiosk (`<audio onEnded>`).
        Trois comportements selon le mode d'enchaînement actif :
        - auto : piste suivante immédiatement ;
        - timer : attente `audio_chain_timer_seconds` puis piste suivante ;
        - manual : la piste reste arrêtée, le coach relance à la main.
        """
        if self.state["current_audio_course"] is None:
            return

        mode = self.state["audio_chain_mode"]
        idx = self.state["audio_track_index"]

        # Idempotent : TOUS les écrans envoient la fin de piste, et
        # le serveur peut l'avoir déjà enchaînée lui-même. Sans cette garde, le
        # signal tardif d'un second écran sautait une piste de plus en mode auto
        # (ou relançait l'attente en mode minuterie). `track_index` = la piste que
        # l'écran vient de terminer ; absent (ancien client), seul l'état « en
        # lecture » est exigé.
        if not self.state["audio_playing"]:
            return
        if track_index is not None and track_index != idx:
            return

        if mode == "manual":
            self.state["audio_playing"] = False
            self._audio_clock.pause()
            await self._emit("audio_track_ended_manual", client_ts)
            return

        if mode == "timer":
            self.state["audio_playing"] = False
            self._audio_clock.pause()
            self.state["audio_chain_wait_remaining"] = float(self.state["audio_chain_timer_seconds"])
            await self._emit("audio_chain_wait_start", client_ts)
            self._audio_chain_wait_task = asyncio.create_task(self._run_audio_chain_wait())
            return

        # mode == "auto"
        if idx is not None and self._goto_track(idx + 1, client_ts):
            await self._emit("audio_next_track", client_ts)
        else:
            self.state["audio_playing"] = False
            self._audio_clock.pause()
            await self._emit("audio_course_ended", client_ts)

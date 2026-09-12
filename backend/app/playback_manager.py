import asyncio
import enum
import logging
import time
from typing import Any, Awaitable, Callable

from app.config import settings

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict], Awaitable[None]]

# Canaux de diffusion indépendants (réf. mission "tableaux de bord Câblé /
# Réseau") : chaque canal a son PROPRE état de lecture, sa propre playlist,
# son propre kiosk primaire. "cable" = l'écran physiquement branché au Wyse,
# "network" = tout /kiosk ouvert depuis un autre appareil du LAN.
CHANNELS = ("cable", "network")
DEFAULT_CHANNEL = "cable"


class PlaybackStateEnum(str, enum.Enum):
    waiting = "waiting"
    playing = "playing"
    paused = "paused"
    coach_mode = "coach_mode"
    offline = "offline"
    playlist_waiting = "playlist_waiting"
    background = "background"  # Lot 7 (F9.2) : fond animé en boucle, plein écran, sans son


def _db_start_session(video_id: int, channel: str, launch_type: str, duration: float) -> int | None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import start_playback_session
        with SessionLocal() as db:
            return start_playback_session(db, video_id, channel, launch_type, duration)
    except Exception as e:
        logger.error(f"Erreur DB start session : {e}")
        return None


def _db_update_session(session_id: int, position: float) -> None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import update_playback_session_progress
        with SessionLocal() as db:
            update_playback_session_progress(db, session_id, position)
    except Exception as e:
        logger.debug(f"Erreur DB update session : {e}")


def _db_close_session(session_id: int, position: float | None = None, completed: bool | None = None) -> None:
    try:
        from app.database import SessionLocal
        from app.utils.playback_session_tracker import close_playback_session
        with SessionLocal() as db:
            close_playback_session(db, session_id, position, completed)
    except Exception as e:
        logger.error(f"Erreur DB close session : {e}")


class PlaybackManager:
    """
    État de lecture global et partagé de l'écran cinéma (Lot 3, réf. plan
    de construction §8.3.1). Le kiosk reste seul maître de la lecture réelle
    (élément <video>) ; ce gestionnaire fait autorité sur l'état logique
    partagé, diffusé à tous les clients (kiosk + télécommandes) via WebSocket.
    """

    def __init__(self, broadcast: BroadcastFn, channel: str = DEFAULT_CHANNEL):
        self._broadcast = broadcast
        # Canal de diffusion que cet état pilote ("cable" ou "network").
        # Chaque évènement émis porte ce champ pour que les clients (kiosks,
        # tableaux de bord) ne réagissent qu'aux évènements de LEUR canal —
        # zéro interférence entre les deux lectures (réf. mission).
        self.channel = channel
        # Session de lecture SQLite active pour ce canal (réf. CDC V3.0.5 §2.3)
        self._current_session_id: int | None = None
        self._last_session_update: float = 0.0
        # Instant (monotonic) du dernier report_position reçu directement du
        # kiosk : seul le kiosk primaire diffuse les position_tick (cf.
        # _position_broadcast_loop).
        self._last_direct_report = 0.0
        self._waiting_task: asyncio.Task | None = None
        self._audio_chain_wait_task: asyncio.Task | None = None
        self._position_broadcast_task: asyncio.Task | None = None
        # Numéro de séquence des `position_tick` de CE canal (réf. retour
        # utilisateur "renforcer le logiciel pour les réseaux imparfaits") :
        # incrémenté à chaque tick émis, jamais réinitialisé (y compris entre
        # deux vidéos). Le client compare ce numéro au précédent reçu — un
        # écart signale un tick perdu en silence (Wi-Fi imparfait) et
        # déclenche une resynchronisation REST immédiate au lieu d'attendre
        # le prochain cycle du filet de sécurité périodique (15s).
        self._tick_seq = 0
        # Fond d'ambiance de repli du cours/playlist EN COURS (réf. mission
        # "associer un fond animé à chaque musique") : celui choisi au
        # lancement (background_id du cours, ou None pour une playlist). Non
        # diffusé directement — sert de repli à `_track_background()` pour
        # les pistes qui n'ont pas de fond qui leur soit propre. Distinct de
        # `current_background` (l'état RÉELLEMENT affiché), qui lui change à
        # chaque piste ayant son propre fond.
        self._default_audio_background: dict[str, Any] | None = None
        self.state: dict[str, Any] = {
            "state": PlaybackStateEnum.waiting.value,
            "current_video": None,
            "position_seconds": 0.0,
            "volume": settings.volume_default,
            "speed": 1.0,
            "playlist_id": None,
            "playlist_name": None,
            "playlist_items": None,
            "playlist_index": None,
            "playlist_waiting_remaining": None,
            "current_background": None,
            # Mode audio coach (Lot 8, réf. F10.3-F10.4)
            "current_audio_course": None,
            "audio_tracks": None,
            "audio_track_index": None,
            "audio_playing": False,
            "audio_position_seconds": 0.0,
            "audio_chain_mode": "auto",
            "audio_chain_timer_seconds": settings.audio_chain_timer_seconds,
            "audio_chain_wait_remaining": None,
        }

    def snapshot(self) -> dict:
        return dict(self.state)

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

    def start_position_broadcast_loop(self):
        """À appeler une fois au démarrage du worker (lifespan FastAPI, réf.
        Phase 5). Diffuse la position à intervalle fixe pendant la lecture,
        plutôt qu'à chaque rapport silencieux du kiosk (cf. report_position)."""
        if self._position_broadcast_task is None or self._position_broadcast_task.done():
            self._position_broadcast_task = asyncio.create_task(self._position_broadcast_loop())

    def stop_position_broadcast_loop(self):
        if self._position_broadcast_task and not self._position_broadcast_task.done():
            self._position_broadcast_task.cancel()
        self._position_broadcast_task = None

    async def _position_broadcast_loop(self):
        try:
            last_tick_time = time.monotonic()
            while True:
                await asyncio.sleep(0.25)
                now = time.monotonic()
                delta = now - last_tick_time
                last_tick_time = now

                is_video_playing = self.state["state"] == PlaybackStateEnum.playing.value
                is_audio_playing = (
                    self.state["state"] == PlaybackStateEnum.coach_mode.value and self.state["audio_playing"]
                )
                drives_playback = time.monotonic() - self._last_direct_report < 2.5
                if is_video_playing and drives_playback:
                    await self._emit("position_tick")
                elif is_audio_playing:
                    if not drives_playback:
                        cur_pos = self.state.get("audio_position_seconds") or 0.0
                        tracks = self.state.get("audio_tracks") or []
                        idx = self.state.get("audio_track_index")
                        track_dur = (
                            tracks[idx].get("duration_seconds")
                            if idx is not None and 0 <= idx < len(tracks)
                            else None
                        )
                        new_pos = cur_pos + delta
                        if track_dur and new_pos >= track_dur:
                            if self.state.get("audio_chain_mode") == "auto":
                                await self.audio_next_track()
                                continue
                            else:
                                new_pos = track_dur
                                self.state["audio_playing"] = False
                        self.state["audio_position_seconds"] = new_pos
                    await self._emit("position_tick")
        except asyncio.CancelledError:
            pass

    def _clear_audio_coach(self):
        """Sort du mode audio coach (réf. F10.4) — appelé par tout ce qui
        prend le relais sur l'écran (cours vidéo, playlist, fond animé,
        arrêt manuel). Ne s'applique PAS à la règle de priorité F10.7, qui
        empêche au contraire une programmation automatique d'appeler ceci."""
        self._cancel_audio_chain_wait()
        self.state["current_audio_course"] = None
        self.state["audio_tracks"] = None
        self.state["audio_track_index"] = None
        self.state["audio_playing"] = False
        self.state["audio_position_seconds"] = 0.0
        self.state["audio_chain_wait_remaining"] = None
        self._default_audio_background = None

    async def load(
        self,
        video_id: int,
        title: str,
        duration_seconds: float | None,
        program: str | None = None,
        client_ts: float | None = None,
        keep_playlist: bool = False,
        thumbnail_url: str | None = None,
        description: str | None = None,
        audio_channels: int | None = None,
        audio_codec: str | None = None,
        fps: float | None = None,
        bitrate_kbps: int | None = None,
        width: int | None = None,
        height: int | None = None,
        launch_type: str = "kiosk",
    ):
        """
        Lance un cours directement en lecture.
        """
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

        self.state["current_video"] = {
            "id": video_id,
            "title": title,
            "duration_seconds": duration_seconds,
            "program": program,
            "thumbnail_url": thumbnail_url,
            "description": description,
            "audio_channels": audio_channels,
            "audio_codec": audio_codec,
            "fps": fps,
            "bitrate_kbps": bitrate_kbps,
            "width": width,
            "height": height,
        }
        self.state["position_seconds"] = 0.0
        self.state["volume"] = self.state.get("volume", settings.volume_default)
        self.state["state"] = PlaybackStateEnum.playing.value

        # Démarrage de la session SQLite d'assiduité (réf. CDC V3.0.5 §2.3)
        self._current_session_id = await asyncio.to_thread(
            _db_start_session, video_id, self.channel, launch_type, duration_seconds or 0.0
        )
        self._last_session_update = time.monotonic()

        await self._emit("load", client_ts)

    async def load_playlist(
        self,
        playlist_id: int,
        playlist_name: str,
        playlist_items: list[dict],
        client_ts: float | None = None,
    ):
        """Lance une playlist : initialise l'index et charge la première vidéo avec compte à rebours."""
        self._cancel_waiting()

        self.state["playlist_id"] = playlist_id
        self.state["playlist_name"] = playlist_name
        self.state["playlist_items"] = playlist_items
        self.state["playlist_index"] = 0
        self.state["playlist_waiting_remaining"] = None

        if not playlist_items:
            await self.stop(client_ts)
            return

        first_item = playlist_items[0]
        await self.load(
            video_id=first_item["id"],
            title=first_item["title"],
            duration_seconds=first_item["duration_seconds"],
            program=first_item.get("program"),
            client_ts=client_ts,
            keep_playlist=True,
            thumbnail_url=first_item.get("thumbnail_url"),
            description=first_item.get("description"),
            audio_channels=first_item.get("audio_channels"),
            audio_codec=first_item.get("audio_codec"),
            fps=first_item.get("fps"),
            bitrate_kbps=first_item.get("bitrate_kbps"),
            width=first_item.get("width"),
            height=first_item.get("height"),
        )

    async def _run_waiting_period(self):
        # Se retient elle-même (réf. correctif "tâche d'attente orpheline
        # entre deux vidéos d'une playlist") : un garde-fou supplémentaire en
        # plus de l'ordonnancement corrigé dans video_ended() (le task est
        # désormais assigné à self._waiting_task avant tout await, pour
        # qu'une commande concurrente — skip_waiting/next_video/previous_video
        # — puisse toujours l'annuler via _cancel_waiting()). Si malgré ça ce
        # task n'est plus celui suivi par le manager (annulé puis remplacé
        # entre deux itérations du sleep), on s'arrête sans jamais avancer la
        # playlist une seconde fois.
        this_task = asyncio.current_task()
        try:
            remaining = self.state["playlist_waiting_remaining"] or 0.0
            while remaining > 0:
                await asyncio.sleep(1.0)
                if self._waiting_task is not this_task:
                    return
                remaining -= 1.0
                self.state["playlist_waiting_remaining"] = max(0.0, remaining)
                await self._emit("playlist_waiting_tick")

            if self._waiting_task is not this_task:
                return
            # Temps d'attente écoulé : lance la vidéo suivante. On détache CE
            # task du manager AVANT l'appel (correctif "timer bloqué à 0 en
            # prod") : _play_next_video() appelle _cancel_waiting(), qui
            # annulerait sinon le task COURANT (lui-même) — la CancelledError
            # serait alors levée au prochain await, à l'intérieur du load()
            # suivant (broadcast). Résultat : l'état passait bien à "playing"
            # en mémoire mais l'évènement "load" n'était JAMAIS diffusé au
            # kiosk, qui restait figé sur « 0 ». En mettant self._waiting_task
            # à None ici, _cancel_waiting() n'a plus rien à annuler et le
            # broadcast aboutit.
            self._waiting_task = None
            await self._play_next_video()
        except asyncio.CancelledError:
            pass

    async def _play_next_video(self, client_ts: float | None = None):
        self._cancel_waiting()

        idx = self.state["playlist_index"]
        items = self.state["playlist_items"]
        if idx is None or items is None:
            await self.stop(client_ts)
            return

        next_idx = idx + 1
        if next_idx < len(items):
            self.state["playlist_index"] = next_idx
            next_item = items[next_idx]
            await self.load(
                video_id=next_item["id"],
                title=next_item["title"],
                duration_seconds=next_item["duration_seconds"],
                program=next_item.get("program"),
                client_ts=client_ts,
                keep_playlist=True,
                thumbnail_url=next_item.get("thumbnail_url"),
                description=next_item.get("description"),
                audio_channels=next_item.get("audio_channels"),
                audio_codec=next_item.get("audio_codec"),
                fps=next_item.get("fps"),
                bitrate_kbps=next_item.get("bitrate_kbps"),
                width=next_item.get("width"),
                height=next_item.get("height"),
            )
        else:
            await self.stop(client_ts)

    async def next_video(self, client_ts: float | None = None):
        """Passe immédiatement à la vidéo suivante de la playlist active."""
        if self.state["playlist_items"] is None or self.state["playlist_index"] is None:
            return
        await self._play_next_video(client_ts)

    async def previous_video(self, client_ts: float | None = None):
        """Revient immédiatement à la vidéo précédente de la playlist active."""
        idx = self.state["playlist_index"]
        items = self.state["playlist_items"]
        if idx is None or items is None or idx - 1 < 0:
            return

        prev_idx = idx - 1
        self.state["playlist_index"] = prev_idx
        prev_item = items[prev_idx]

        self._cancel_waiting()

        await self.load(
            video_id=prev_item["id"],
            title=prev_item["title"],
            duration_seconds=prev_item["duration_seconds"],
            program=prev_item.get("program"),
            client_ts=client_ts,
            keep_playlist=True,
            thumbnail_url=prev_item.get("thumbnail_url"),
            description=prev_item.get("description"),
            audio_channels=prev_item.get("audio_channels"),
            audio_codec=prev_item.get("audio_codec"),
            fps=prev_item.get("fps"),
            bitrate_kbps=prev_item.get("bitrate_kbps"),
            width=prev_item.get("width"),
            height=prev_item.get("height"),
        )

    async def skip_waiting(self, client_ts: float | None = None):
        """Passe immédiatement le compte à rebours d'attente intercalée."""
        if self.state["state"] != PlaybackStateEnum.playlist_waiting.value:
            return
        await self._play_next_video(client_ts)

    async def video_ended(self, client_ts: float | None = None):
        """Gère la fin naturelle d'une vidéo signalée par le kiosk."""
        self._cancel_waiting()

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
        # En mode coach (Lot 8), "Lecture" pilote la piste audio en cours
        # plutôt que la vidéo — même bouton, comportement contextuel (UX5.1 :
        # un seul état partagé, pas de mode de contrôle séparé par écran).
        if self.state["current_audio_course"] is not None:
            self.state["audio_playing"] = True
            await self._emit("play", client_ts)
            return
        if (
            self.state["current_video"] is None
            or self.state["state"] == PlaybackStateEnum.playlist_waiting.value
        ):
            return
        self.state["state"] = PlaybackStateEnum.playing.value
        await self._emit("play", client_ts)

    async def pause(self, client_ts: float | None = None):
        if self.state["current_audio_course"] is not None:
            self.state["audio_playing"] = False
            await self._emit("pause", client_ts)
            return
        if (
            self.state["current_video"] is None
            or self.state["state"] == PlaybackStateEnum.playlist_waiting.value
        ):
            return
        self.state["state"] = PlaybackStateEnum.paused.value
        await self._emit("pause", client_ts)

    async def stop(self, client_ts: float | None = None):
        self._cancel_waiting()
        self._clear_audio_coach()

        # Clôture de la session d'assiduité avec position finale
        if self._current_session_id is not None:
            sess_id = self._current_session_id
            self._current_session_id = None
            pos = self.state.get("position_seconds", 0.0)
            asyncio.create_task(asyncio.to_thread(_db_close_session, sess_id, pos))

        self.state["state"] = PlaybackStateEnum.waiting.value
        self.state["current_video"] = None
        self.state["position_seconds"] = 0.0
        self.state["playlist_id"] = None
        self.state["playlist_name"] = None
        self.state["playlist_items"] = None
        self.state["playlist_index"] = None
        self.state["playlist_waiting_remaining"] = None
        self.state["current_background"] = None
        await self._emit("stop", client_ts)

    async def load_background(self, background_id: int, title: str, is_image: bool = False, client_ts: float | None = None):
        """Lance un fond animé en boucle infinie, plein écran, sans son (réf.
        F9.2). Prend le relais immédiatement sur toute lecture en cours — pas
        de compte à rebours, une boucle d'ambiance n'est pas un « lancement de
        cours » (UX2.8 ne s'applique qu'aux vidéos de cours). `is_image`
        (réf. mission "fond figé ou animé") : le kiosk rend une <img> figée
        plutôt qu'une <video> en boucle quand ce fond est une image fixe."""
        self._cancel_waiting()
        self._clear_audio_coach()
        self.state["state"] = PlaybackStateEnum.background.value
        self.state["current_video"] = None
        self.state["position_seconds"] = 0.0
        self.state["playlist_id"] = None
        self.state["playlist_name"] = None
        self.state["playlist_items"] = None
        self.state["playlist_index"] = None
        self.state["playlist_waiting_remaining"] = None
        self.state["current_background"] = {"id": background_id, "title": title, "is_image": is_image}
        await self._emit("load_background", client_ts)

    async def seek(self, position_seconds: float, client_ts: float | None = None):
        if self.state["current_video"] is None or self.state["state"] == PlaybackStateEnum.playlist_waiting.value:
            return
        duration = self.state["current_video"].get("duration_seconds")
        position_seconds = max(0.0, position_seconds)
        if duration:
            position_seconds = min(position_seconds, duration)
        self.state["position_seconds"] = position_seconds
        await self._emit("seek", client_ts)

    async def set_volume(self, volume: float, client_ts: float | None = None):
        self.state["volume"] = max(0, min(100, int(volume)))
        await self._emit("volume", client_ts)

    async def set_speed(self, speed: float, client_ts: float | None = None):
        self.state["speed"] = max(0.25, min(2.0, float(speed)))
        await self._emit("speed", client_ts)

    async def report_position(self, position_seconds: float):
        """
        Rapport de la position réelle par le kiosk (plusieurs fois par
        seconde). Vraiment silencieux depuis la Phase 5 (P5) : met à jour
        l'état en mémoire mais NE diffuse PAS aux clients à chaque appel —
        _position_broadcast_loop s'en charge à intervalle fixe. Un broadcast
        systématique ici saturerait les télécommandes pour un gain de
        précision inutile.
        """
        if self.state["current_video"] is None or self.state["state"] == PlaybackStateEnum.playlist_waiting.value:
            return
        now_mono = time.monotonic()
        self._last_direct_report = now_mono
        self.state["position_seconds"] = position_seconds

        # Throttling de la mise à jour en base toutes les 5s
        if self._current_session_id is not None and (now_mono - self._last_session_update >= 5.0):
            self._last_session_update = now_mono
            asyncio.create_task(asyncio.to_thread(_db_update_session, self._current_session_id, position_seconds))

    # ------------------------------------------------------------------
    # Mode audio coach (Lot 8, réf. F10.3/F10.4/UX4.5-4.9)
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
        la première piste (réf. F10.4 « lancer en 2 taps maximum » — le choix
        du cours suffit, pas de tap Lecture supplémentaire nécessaire).
        `current_background` est peuplé au même format que load_background()
        (réf. mission "fond figé ou animé" du mode coach) : le kiosk n'a plus
        qu'UNE seule source de vérité pour rendre le fond, qu'on soit en mode
        "background" pur ou en mode coach avec fond d'ambiance."""
        self._cancel_waiting()
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
        # Fond RÉELLEMENT affiché pour la première piste (réf. mission
        # "associer un fond animé à chaque musique") : peut différer du fond
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
        """Lance une playlist audio ("édition mixée", réf. mission "playlists
        spéciales... des musiques de plusieurs RPM différents, pas juste
        plusieurs RPM collés") : une playlist est une séquence de PISTES
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
        """Fond à afficher pour CETTE piste (réf. mission "associer un fond
        animé à chaque musique") : le sien propre s'il en a un, sinon le fond
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
            # mais en pause (réf. F10.3, pas d'arrêt automatique du mode coach).
            self._cancel_audio_chain_wait()
            self.state["audio_playing"] = False
            await self._emit("audio_course_ended", client_ts)

    async def audio_previous_track(self, client_ts: float | None = None):
        idx = self.state["audio_track_index"]
        if idx is None:
            return
        if self._goto_track(idx - 1, client_ts):
            await self._emit("audio_previous_track", client_ts)

    async def audio_restart_track(self, client_ts: float | None = None):
        """Relance la piste en cours depuis le début (réf. UX4.6)."""
        if self.state["audio_track_index"] is None:
            return
        self._cancel_audio_chain_wait()
        self.state["audio_position_seconds"] = 0.0
        self.state["audio_playing"] = True
        await self._emit("audio_restart_track", client_ts)

    async def audio_jump_to_track(self, index: int, client_ts: float | None = None):
        """Saut direct à une piste depuis la liste (bottom sheet, réf. UX4.7)."""
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
        lecture (réf. mission "ajoute la possibilité d'afficher un fond
        depuis le mode coach") — sans ça, le fond n'était fixé qu'au
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
        """Même logique silencieuse que report_position (réf. Phase 5, P5),
        côté piste audio."""
        if self.state["current_audio_course"] is None:
            return
        self._last_direct_report = time.monotonic()
        self.state["audio_position_seconds"] = position_seconds

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
                await self._emit("audio_course_ended")
        except asyncio.CancelledError:
            pass

    async def audio_track_ended(self, client_ts: float | None = None):
        """
        Fin naturelle d'une piste signalée par le kiosk (`<audio onEnded>`).
        Trois comportements selon le mode d'enchaînement actif (réf. F10.3,
        UX4.8) :
        - auto : piste suivante immédiatement ;
        - timer : attente `audio_chain_timer_seconds` puis piste suivante ;
        - manual : la piste reste arrêtée, le coach relance à la main.
        """
        if self.state["current_audio_course"] is None:
            return

        mode = self.state["audio_chain_mode"]
        idx = self.state["audio_track_index"]

        if mode == "manual":
            self.state["audio_playing"] = False
            await self._emit("audio_track_ended_manual", client_ts)
            return

        if mode == "timer":
            self.state["audio_playing"] = False
            self.state["audio_chain_wait_remaining"] = float(self.state["audio_chain_timer_seconds"])
            await self._emit("audio_chain_wait_start", client_ts)
            self._audio_chain_wait_task = asyncio.create_task(self._run_audio_chain_wait())
            return

        # mode == "auto"
        if idx is not None and self._goto_track(idx + 1, client_ts):
            await self._emit("audio_next_track", client_ts)
        else:
            self.state["audio_playing"] = False
            await self._emit("audio_course_ended", client_ts)


_managers: dict[str, PlaybackManager] = {}


def init_playback_managers(broadcast: BroadcastFn) -> dict[str, PlaybackManager]:
    """Crée les deux gestionnaires d'état, un par canal de diffusion (réf.
    mission "tableaux de bord Câblé / Réseau" : deux lectures totalement
    indépendantes, chacune avec sa playlist, sa position, son volume)."""
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

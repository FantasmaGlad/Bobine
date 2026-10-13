import asyncio
import enum
import logging
import time
from typing import Any, Awaitable, Callable

from app.config import settings
from app.utils.playback_clock import PlaybackClock

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict], Awaitable[None]]

# Canaux de diffusion indépendants (réf. mission "tableaux de bord Câblé /
# Réseau") : chaque canal a son PROPRE état de lecture, sa propre playlist,
# son propre kiosk primaire. "cable" = l'écran physiquement branché au Wyse,
# "network" = tout /kiosk ouvert depuis un autre appareil du LAN.
CHANNELS = ("cable", "network")
DEFAULT_CHANNEL = "cable"


# Décalage (ms) entre l'ordre reçu et l'instant où TOUS les écrans démarrent
# (réf. plan 4.0, P2-2) : laisse à chaque écran le temps de recevoir l'ordre
# pour qu'ils démarrent ENSEMBLE plutôt que « au plus vite » chacun de son côté.
# Il n'a de sens qu'avec PLUSIEURS écrans : avec un seul (ou aucun), tout délai
# n'est que de la latence ressentie — mesuré 300 ms sur play et 1 000 ms au
# chargement avec un délai fixe, contre 1 à 3 ms sur pause — donc nul (cf.
# `PlaybackManager._lead_ms`). Court pour play/seek (média déjà chargé), un peu
# plus long pour un nouveau cours (il faut ouvrir le flux).
LOAD_LEAD_MS = 400.0
PLAY_LEAD_MS = 150.0
SEEK_LEAD_MS = 150.0
# Cadence du heartbeat de position pendant la lecture vidéo : chaque écran
# recalcule seul sa position à partir de l'horloge ; le heartbeat ne sert qu'à
# ré-ancrer les arrivants et à rattraper un évènement perdu.
VIDEO_HEARTBEAT_SECONDS = 1.0
# Marge au-delà de la durée avant que le SERVEUR déclare lui-même la fin d'un
# cours (filet de sécurité si aucun écran n'envoie `video_ended`, p. ex. aucun
# kiosque connecté sur le canal).
VIDEO_END_GRACE_SECONDS = 3.0
# Même filet de sécurité pour une piste audio du mode coach : les écrans
# signalent la fin de piste au bon moment ; si aucun ne le fait (aucun écran
# connecté, pistes en mise en mémoire tampon) le serveur l'enchaîne lui-même.
AUDIO_END_GRACE_SECONDS = 2.0


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
        # Horloge de lecture vidéo (réf. plan 4.0, P2-2) : source de vérité de
        # la position, indépendante de tout kiosque.
        self._clock = PlaybackClock()
        # Horloge de la piste audio du mode coach (plan 4.0.1) : même modèle que
        # la vidéo — la position est une fonction du temps, plus la dernière
        # valeur rapportée par un écran primaire.
        self._audio_clock = PlaybackClock()
        self._last_heartbeat = 0.0
        # Nombre d'écrans de diffusion connectés sur CE canal (fourni par la
        # couche WebSocket) : décide si un démarrage synchronisé est utile.
        self.display_counter: Callable[[str], int] = lambda channel: 0
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
            # Réf. CDC planning visuel (2026-09-17) §5.3 : distingue "lecture
            # manuelle" d'un "reliquat d'une programmation encore en cours"
            # pour la détection de conflit de scheduler_manager._launch_target
            # — sans ce marqueur, la règle réseau "le manuel gagne toujours"
            # s'appliquait aussi à tort à un chevauchement programmation vs
            # programmation, annulant silencieusement la seconde au lieu de
            # la laisser couper proprement la première.
            "scheduled_launch": False,
        }

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
                if is_video_playing:
                    # Vidéo : l'horloge serveur avance seule, qu'un kiosque
                    # rapporte ou non — heartbeat lent, pas de tick à 4 Hz.
                    if now - self._last_heartbeat >= VIDEO_HEARTBEAT_SECONDS:
                        self._last_heartbeat = now
                        if await self._end_video_if_overdue():
                            continue
                        await self._emit("position_tick")
                elif is_audio_playing:
                    # Audio coach : l'horloge serveur avance seule (plan 4.0.1) ;
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
        self._audio_clock.reset()
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
        scheduled: bool = False,
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
        self.state["scheduled_launch"] = scheduled
        self._clock.reset()
        self._clock.set_rate(self.state["speed"])
        self._clock.start(0.0, lead_ms=self._lead_ms(LOAD_LEAD_MS))
        self._last_heartbeat = time.monotonic()

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
        scheduled: bool = False,
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
            scheduled=scheduled,
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
            # Réf. "scheduled_launch" ci-dessus : relu AVANT l'appel qui va le
            # réécrire, pour que l'avance automatique/manuelle au sein d'une
            # MÊME playlist ne perde jamais l'origine "programmation" de la
            # lecture en cours.
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
                scheduled=self.state.get("scheduled_launch", False),
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
            scheduled=self.state.get("scheduled_launch", False),
        )

    async def skip_waiting(self, client_ts: float | None = None):
        """Passe immédiatement le compte à rebours d'attente intercalée."""
        if self.state["state"] != PlaybackStateEnum.playlist_waiting.value:
            return
        await self._play_next_video(client_ts)

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
        # En mode coach (Lot 8), "Lecture" pilote la piste audio en cours
        # plutôt que la vidéo — même bouton, comportement contextuel (UX5.1 :
        # un seul état partagé, pas de mode de contrôle séparé par écran).
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
        self._clock.reset()
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
        self._clock.seek(position_seconds, lead_ms=self._lead_ms(SEEK_LEAD_MS) if self._clock.running else 0.0)
        self._last_heartbeat = time.monotonic()
        await self._emit("seek", client_ts)

    async def set_volume(self, volume: float, client_ts: float | None = None):
        self.state["volume"] = max(0, min(100, int(volume)))
        await self._emit("volume", client_ts)

    async def set_speed(self, speed: float, client_ts: float | None = None):
        self.state["speed"] = max(0.25, min(2.0, float(speed)))
        self._clock.set_rate(self.state["speed"])
        await self._emit("speed", client_ts)

    async def report_position(self, position_seconds: float):
        """
        Rapport de la position réelle d'un écran (kiosque primaire).

        Depuis le lot P2-2 la position est portée par l'horloge serveur
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
        self._audio_clock.reset()
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
            # mais en pause (réf. F10.3, pas d'arrêt automatique du mode coach).
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
        """Relance la piste en cours depuis le début (réf. UX4.6)."""
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
        # Plan 4.0.1 : la position audio vient de l'horloge serveur ; ce rapport
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

        # Idempotent (plan 4.0.1) : TOUS les écrans envoient la fin de piste, et
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

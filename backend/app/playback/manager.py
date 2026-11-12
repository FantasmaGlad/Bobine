"""Gestionnaire de lecture d'un canal de diffusion, et registre des gestionnaires par canal."""
import asyncio
import logging
from typing import Any, Callable
from app.config import settings
from app.utils.playback_clock import PlaybackClock
from app.utils.radio_sound import default_sound
# Canaux de diffusion indépendants, chacun avec son état, sa playlist et son kiosque primaire : « cable » (écran
# branché à la machine), « network » (tout /kiosk ouvert depuis un autre appareil du réseau local).
from app.api.contract import CHANNELS, DEFAULT_CHANNEL
from app.playback.constants import BroadcastFn, PlaybackStateEnum
from app.playback.state import StateMixin
from app.playback.broadcast import BroadcastMixin
from app.playback.video import VideoMixin
from app.playback.playlist import PlaylistMixin
from app.playback.audio import AudioMixin
from app.playback.controls import ControlsMixin

logger = logging.getLogger(__name__)


class PlaybackManager(VideoMixin, PlaylistMixin, AudioMixin, ControlsMixin, BroadcastMixin, StateMixin):
    """
    État de lecture global et partagé de l'écran cinéma. Le kiosk reste seul maître de la lecture réelle
    (élément <video>) ; ce gestionnaire fait autorité sur l'état logique
    partagé, diffusé à tous les clients (kiosk + télécommandes) via WebSocket.
    """

    def __init__(self, broadcast: BroadcastFn, channel: str = DEFAULT_CHANNEL):
        self._broadcast = broadcast
        # Canal de diffusion que cet état pilote ("cable" ou "network").
        # Chaque évènement émis porte ce champ pour que les clients (kiosks,
        # tableaux de bord) ne réagissent qu'aux évènements de LEUR canal —
        # zéro interférence entre les deux lectures.
        self.channel = channel
        # Session de lecture SQLite active pour ce canal
        self._current_session_id: int | None = None
        self._last_session_update: float = 0.0
        # Instant (monotonic) du dernier report_position reçu directement du
        # kiosk : seul le kiosk primaire diffuse les position_tick (cf.
        # _position_broadcast_loop).
        self._last_direct_report = 0.0
        self._scheduled_launch_recorded = False
        self._waiting_task: asyncio.Task | None = None
        self._audio_chain_wait_task: asyncio.Task | None = None
        self._position_broadcast_task: asyncio.Task | None = None
        # Numéro de séquence des `position_tick` de CE canal :
        # incrémenté à chaque tick émis, jamais réinitialisé (y compris entre
        # deux vidéos). Le client compare ce numéro au précédent reçu — un
        # écart signale un tick perdu en silence (Wi-Fi imparfait) et
        # déclenche une resynchronisation REST immédiate au lieu d'attendre
        # le prochain cycle du filet de sécurité périodique (15s).
        self._tick_seq = 0
        # Horloge de lecture vidéo : source de vérité de
        # la position, indépendante de tout kiosque.
        self._clock = PlaybackClock()
        # Horloge de la piste audio du mode coach : même modèle que
        # la vidéo — la position est une fonction du temps, plus la dernière
        # valeur rapportée par un écran primaire.
        self._audio_clock = PlaybackClock()
        self._last_heartbeat = 0.0
        # Nombre d'écrans de diffusion connectés sur CE canal (fourni par la
        # couche WebSocket) : décide si un démarrage synchronisé est utile.
        self.display_counter: Callable[[str], int] = lambda channel: 0
        # Fond d'ambiance de repli du cours/playlist EN COURS : celui choisi au
        # lancement (background_id du cours, ou None pour une playlist). Non
        # diffusé directement — sert de repli à `_track_background()` pour
        # les pistes qui n'ont pas de fond qui leur soit propre. Distinct de
        # `current_background` (l'état RÉELLEMENT affiché), qui lui change à
        # chaque piste ayant son propre fond.
        self._default_audio_background: dict[str, Any] | None = None
        self.state: dict[str, Any] = {
            "state": PlaybackStateEnum.waiting.value,
            "current_video": None,
            # Sous-titres du cours en cours, choisis depuis l'admin : None = piste
            # par défaut (première importée), "off" = aucun, sinon identifiant
            # d'une piste. Remis à None à chaque nouveau cours.
            "subtitle": None,
            "position_seconds": 0.0,
            "volume": settings.volume_default,
            # Réglages de son du canal (égaliseur, basses, loudness, limiteur) : validés par utils/video_sound.py,
            # appliqués par le lecteur (graphe Web Audio).
            "sound": default_sound(),
            "speed": 1.0,
            "playlist_id": None,
            "playlist_name": None,
            "playlist_items": None,
            "playlist_index": None,
            "playlist_waiting_remaining": None,
            "current_background": None,
            # Mode audio coach
            "current_audio_course": None,
            "audio_tracks": None,
            "audio_track_index": None,
            "audio_playing": False,
            "audio_position_seconds": 0.0,
            "audio_chain_mode": "auto",
            "audio_chain_timer_seconds": settings.audio_chain_timer_seconds,
            "audio_chain_wait_remaining": None,
            # distingue "lecture
            # manuelle" d'un "reliquat d'une programmation encore en cours"
            # pour la détection de conflit de scheduling.launch.launch_target
            # — sans ce marqueur, la règle réseau "le manuel gagne toujours"
            # s'appliquait aussi à tort à un chevauchement programmation vs
            # programmation, annulant silencieusement la seconde au lieu de
            # la laisser couper proprement la première.
            "scheduled_launch": False,
        }


_managers: dict[str, PlaybackManager] = {}


def init_playback_managers(broadcast: BroadcastFn) -> dict[str, PlaybackManager]:
    """Crée les deux gestionnaires d'état, un par canal de diffusion."""
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

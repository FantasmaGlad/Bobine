"""Constantes de la lecture : délais de synchronisation, battements, états."""
import enum
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


BroadcastFn = Callable[[dict], Awaitable[None]]


# Décalage (ms) entre l'ordre reçu et l'instant où TOUS les écrans démarrent : laisse à chaque écran le temps de recevoir l'ordre
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
    background = "background"  # fond animé en boucle, plein écran, sans son

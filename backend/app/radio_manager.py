"""Moteur de lecture du canal Radio.

Sous-système INDÉPENDANT du PlaybackManager câblé/réseau : un
3e canal `radio` avec sa propre sémantique musicale — playlist, ordre de lecture
(shuffle), répétition (piste/playlist), file d'attente « à suivre », volume.

Comme le PlaybackManager, il fait autorité sur l'ÉTAT LOGIQUE partagé (diffusé à
tous les clients via WebSocket). La lecture audio réelle est faite par l'écran
`/radio` : il rapporte la position et signale la fin de piste
(`radio_track_ended`), le moteur avance alors selon repeat/shuffle/queue.
"""
import asyncio
import logging
import random
import time
from typing import Any, Awaitable, Callable

from app.config import settings
from app.storage.availability import media_available
from app.utils.playback_clock import PlaybackClock
from app.utils.radio_mix import default_mix
from app.utils.radio_sound import default_sound

logger = logging.getLogger(__name__)

BroadcastFn = Callable[[dict], Awaitable[None]]

# Deux moteurs radio INDÉPENDANTS, un par sortie de diffusion (même modèle que
# les gestionnaires câblé/réseau de playback_manager.py) : la sortie câblée
# (écran physiquement connecté) et la sortie réseau (tout autre appareil) ont
# chacune leur playlist, file d'attente, position, volume, rappels et planning.
RADIO_CHANNELS = ("radio_cable", "radio_network")
# Identifiant historique du poste radio unique (avant les deux sorties) : il
# désignait ce qui est aujourd'hui la sortie réseau. Il reste accepté en ENTRÉE
# (anciens favoris, onglets ouverts, planning, clients en cache) et n'est
# jamais émis.
LEGACY_RADIO_CHANNEL = "radio"
DEFAULT_RADIO_CHANNEL = "radio_network"


def normalize_radio_channel(value: Any) -> str:
    """Identifiant de sortie radio canonique : l'alias historique `radio` devient
    `radio_network` ; toute valeur absente ou inconnue retombe sur le défaut.
    Point UNIQUE de normalisation — aucune table de correspondance ailleurs."""
    if value in RADIO_CHANNELS:
        return value
    return DEFAULT_RADIO_CHANNEL


# Sortie visée par une règle de rappel : une sortie précise ou les deux.
RULE_TARGET_BOTH = "both"
RULE_TARGETS = (*RADIO_CHANNELS, RULE_TARGET_BOTH)


def normalize_rule_target(value: Any) -> str:
    """Cible d'une règle de rappel. L'alias historique `radio` et toute valeur
    inconnue retombent sur la sortie réseau (comportement d'avant les deux sorties)."""
    if value == RULE_TARGET_BOTH:
        return RULE_TARGET_BOTH
    return normalize_radio_channel(value)


def rule_targets_output(target: Any, radio_channel: str) -> bool:
    """Vrai si une règle de rappel de cible `target` s'applique à la sortie `radio_channel`."""
    normalized = normalize_rule_target(target)
    return normalized == RULE_TARGET_BOTH or normalized == normalize_radio_channel(radio_channel)


def is_radio_channel(value: Any) -> bool:
    """Vrai pour un identifiant de sortie radio, alias historique compris."""
    return value == LEGACY_RADIO_CHANNEL or value in RADIO_CHANNELS

REPEAT_MODES = ("off", "playlist", "track")

# Même modèle que la vidéo et l'audio coach : la position d'une
# piste est une fonction du temps (horloge serveur), plus la dernière valeur
# rapportée par le poste /radio primaire.
HEARTBEAT_SECONDS = 1.0
# Marge au-delà de la durée avant que le SERVEUR enchaîne lui-même la piste
# (aucun poste connecté, ou poste bloqué) ; les postes signalent la fin au bon
# moment, ce filet ne sert que s'ils ne le font pas.
TRACK_END_GRACE_SECONDS = 2.0
# Démarrage synchronisé : seulement s'il y a au moins deux postes /radio à
# caler entre eux (sinon réponse immédiate).
PLAY_LEAD_MS = 150.0
# Bail du vumètre : une interface de mixage le renouvelle toutes les quelques secondes tant qu'elle est ouverte ; sans
# renouvellement le lecteur cesse de mesurer (aucun coût quand personne ne regarde).
METER_LEASE_SECONDS = 12.0


class RadioPlaybackManager:
    def __init__(self, broadcast: BroadcastFn, channel: str = DEFAULT_RADIO_CHANNEL):
        self._broadcast = broadcast
        # Sortie radio que ce moteur pilote (`radio_cable` ou `radio_network`) :
        # portée par chaque évènement émis pour que les clients ne réagissent
        # qu'aux évènements de LEUR sortie.
        self.channel = normalize_radio_channel(channel)
        self._last_direct_report = 0.0
        self._clock = PlaybackClock()
        # Nombre de postes /radio connectés (fourni par la couche WebSocket).
        self.display_counter: Callable[[str], int] = lambda channel: 0
        # Chemin de fin de piste du routeur (rappels inclus), pour le filet serveur.
        self.track_end_handler: Callable[[int | None], Awaitable[None]] | None = None
        self._position_broadcast_task: asyncio.Task | None = None
        # Avance différée : la fin
        # de piste qui a déclenché le rappel n'avance PAS tout de suite — cet
        # indicateur interne (pas de self.state : pur détail d'orchestration,
        # jamais utile au client) fait patienter l'avancement jusqu'à la fin du
        # rappel (`announcement_ended`).
        self._deferred_advance_pending = False
        self.state: dict[str, Any] = {
            "state": "idle",            # idle | playing | paused | announcing
            "playlist_id": None,
            "playlist_name": None,
            "order": [],                # ordre de lecture courant (liste de pistes)
            "index": None,              # position courante dans `order`
            "current_track": None,      # = order[index] (confort client)
            "position_seconds": 0.0,
            "duration_seconds": None,   # durée de la piste courante (confort client)
            "volume": settings.radio_volume_default,
            "shuffle": False,
            "repeat": "off",            # off | playlist | track
            "playing": False,
            # Réglages transmis au lecteur /radio (lots L4/L5).
            "crossfade_seconds": settings.radio_crossfade_seconds,
            # Rappels : {id, description, mode} | None. `mode` =
            # "wait_end" (« toutes les N musiques », inséré entre 2 pistes,
            # musique déjà arrêtée) ou "duck" (X min/heures fixes/manuel, fondu
            # immédiat pendant que la musique continue).
            "current_announcement": None,
            # Compteur de la règle « toutes les N musiques »,
            # remis à zéro à chaque rappel joué, quel que soit son mode.
            "tracks_since_announcement": 0,
            # Réglages de son de CETTE sortie (égaliseur, basses…) : appliqués par
            # le lecteur, stockés/validés par utils/radio_sound.py.
            "sound": default_sound(),
            # Table de mixage de la sortie (utils/radio_mix.py) et route audio choisie (devices/routing.py) : appliquées par
            # le lecteur, publiées avec l'état comme le son. `meter` = un vumètre est ouvert (le lecteur mesure ses niveaux).
            "mix": default_mix(),
            "route": None,
            "meter": False,
        }
        self._meter_until = 0.0

    # ------------------------------------------------------------------
    # Diffusion
    # ------------------------------------------------------------------
    def _lead_ms(self, nominal_ms: float) -> float:
        try:
            return nominal_ms if self.display_counter(self.channel) >= 2 else 0.0
        except Exception:
            return 0.0

    def _refresh_position(self) -> None:
        """Aligne `state["position_seconds"]` (champ historique) sur l'horloge."""
        if self.state["current_track"] is None or self.state["state"] not in ("playing", "paused", "announcing"):
            return
        pos = self._clock.position()
        duration = self.state.get("duration_seconds")
        if duration:
            pos = min(pos, duration)
        self.state["position_seconds"] = pos

    def _start_clock(self, position: float = 0.0) -> None:
        """(Re)démarre l'horloge d'une piste ; sans écran à caler, immédiatement."""
        self._clock.reset()
        self._clock.start(position, lead_ms=self._lead_ms(PLAY_LEAD_MS))

    def snapshot(self) -> dict:
        self._refresh_position()
        snap = dict(self.state)
        snap["channel"] = self.channel
        snap["clock"] = self._clock.to_dict()
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
        await self._broadcast(payload)

    # ------------------------------------------------------------------
    # Boucle de diffusion de la position (pour la barre de progression live)
    # ------------------------------------------------------------------
    def start_position_broadcast_loop(self):
        if self._position_broadcast_task is None or self._position_broadcast_task.done():
            self._position_broadcast_task = asyncio.create_task(self._position_broadcast_loop())

    def stop_position_broadcast_loop(self):
        if self._position_broadcast_task and not self._position_broadcast_task.done():
            self._position_broadcast_task.cancel()
        self._position_broadcast_task = None

    async def _position_broadcast_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                await self._expire_meter()
                # L'horloge serveur avance seule : heartbeat tant qu'une piste
                # est en lecture, qu'un poste /radio rapporte ou non.
                if self.state["playing"]:
                    if await self._end_track_if_overdue():
                        continue
                    await self._emit("radio_position_tick")
        except asyncio.CancelledError:
            pass

    async def _end_track_if_overdue(self) -> bool:
        """Filet de sécurité : enchaîne la piste côté serveur si sa durée est
        dépassée d'une marge sans qu'aucun poste n'ait signalé la fin. Inactif
        pendant un rappel (la musique est alors gérée par le rappel)."""
        if self.state["state"] != "playing":
            return False
        track = self.state["current_track"]
        duration = self.state.get("duration_seconds")
        if track is None or not duration or self._clock.position() < duration + TRACK_END_GRACE_SECONDS:
            return False
        logger.info("Radio : fin de piste déclenchée par l'horloge serveur")
        # Même chemin que la commande `radio_track_ended` (règle « toutes les N
        # musiques » incluse) quand le routeur l'a branché ; sinon avancement simple.
        if self.track_end_handler is not None:
            await self.track_end_handler(track.get("id"))
        else:
            await self.track_ended(track_id=track.get("id"))
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _sync_current(self):
        order = self.state["order"]
        idx = self.state["index"]
        if order and idx is not None and 0 <= idx < len(order):
            self.state["current_track"] = order[idx]
            self.state["duration_seconds"] = order[idx].get("duration_seconds")
        else:
            self.state["current_track"] = None
            self.state["duration_seconds"] = None

    def _advance_index(self) -> bool:
        """Avance à la piste suivante en respectant repeat=playlist/shuffle, en SAUTANT les morceaux d'un support
        externe débranché (registre en mémoire). Renvoie False si fin atteinte sans répétition (rien à jouer ensuite)."""
        order = self.state["order"]
        if not order:
            return False
        i = self.state["index"] or 0
        for _ in range(len(order) + 1):
            i += 1
            if i >= len(order):
                if self.state["repeat"] == "playlist":
                    if self.state["shuffle"]:
                        random.shuffle(order)
                    i = 0
                else:
                    return False
            if media_available(order[i].get("storage_id")):
                self.state["index"] = i
                return True
        return False

    # ------------------------------------------------------------------
    # Commandes
    # ------------------------------------------------------------------
    async def load_playlist(self, playlist_id: int, name: str, tracks: list[dict],
                            shuffle: bool | None = None, client_ts: float | None = None,
                            repeat: str | None = None, start_paused: bool = False):
        """`repeat`, si fourni, force le mode de répétition APRÈS chargement
        (ambiance 24/7 par défaut et fenêtres de Planning radio, toutes deux
        censées boucler plutôt que s'arrêter en silence en fin de playlist).
        `start_paused` charge la playlist SANS la lancer : utilisé quand la
        sortie ne diffuse pas la radio (sortie câblée sur kiosk/cinéma) — la
        lecture reprendra à la bascule vers Radio plutôt que de tourner dans le
        vide."""
        if shuffle is not None:
            self.state["shuffle"] = bool(shuffle)
        if repeat is not None:
            self.state["repeat"] = repeat
        order = [t for t in tracks if media_available(t.get("storage_id"))]
        if self.state["shuffle"]:
            random.shuffle(order)
        self.state["playlist_id"] = playlist_id
        self.state["playlist_name"] = name
        self.state["order"] = order
        self.state["index"] = 0 if order else None
        self.state["position_seconds"] = 0.0
        playing = bool(order) and not start_paused
        self.state["playing"] = playing
        self.state["state"] = ("playing" if playing else "paused") if order else "idle"
        # Un rappel en cours (mode wait_end en particulier) n'a plus de sens
        # une fois la playlist remplacée.
        self.state["current_announcement"] = None
        self._deferred_advance_pending = False
        self._sync_current()
        if playing:
            self._start_clock(0.0)
        else:
            self._clock.reset()
        await self._emit("radio_load_playlist", client_ts)

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
        """Passage manuel : boucle en fin de liste même sans répétition (geste
        volontaire du DJ), contrairement à la fin de piste automatique."""
        if not self.state["order"]:
            return
        if not self._advance_index():
            self.state["index"] = 0  # wrap manuel
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
        # Au-delà de 3 s, « précédent » redémarre la piste courante (comme Spotify).
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
        """Avance à la piste suivante ou s'arrête en fin de playlist (partagé
        entre la fin de piste normale et la reprise après un rappel « toutes
        les N musiques »)."""
        if self._advance_index():
            self.state["position_seconds"] = 0.0
            self.state["playing"] = True
            self.state["state"] = "playing"
            self._sync_current()
            self._start_clock(0.0)
            await self._emit("radio_next_track", client_ts)
        else:
            # Fin de playlist, pas de répétition : on s'arrête sur la dernière.
            self.state["playing"] = False
            self.state["state"] = "paused"
            self.state["position_seconds"] = 0.0
            self._clock.reset()
            await self._emit("radio_ended", client_ts)

    async def track_ended(self, client_ts: float | None = None, track_id: int | None = None):
        """Fin de piste rapportée par un lecteur /radio : enchaînement auto.

        Idempotent : CHAQUE page /radio envoie la fin de piste, et
        le serveur peut l'avoir déjà enchaînée lui-même. `track_id` = la piste
        que le poste vient de terminer ; si ce n'est plus la piste courante, le
        signal est périmé et ignoré (sans cela, un poste en retard sautait une
        piste de plus). Absent (ancien client), seul l'état est vérifié."""
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

    # ------------------------------------------------------------------
    # Rappels
    # ------------------------------------------------------------------
    async def play_announcement(
        self, announcement: dict, mode: str, client_ts: float | None = None, deferred_advance: bool = False,
    ):
        """Déclenche un rappel. `mode` = "wait_end" (la piste vient de se
        terminer, `deferred_advance=True` fait patienter l'avancement jusqu'à
        `announcement_ended`) ou "duck" (X min/heures fixes/manuel : la
        musique continue, le fondu est géré côté lecteur /radio). Le compteur
        « toutes les N musiques » est remis à zéro par TOUT rappel joué,
        pas seulement ceux déclenchés par cette règle."""
        self.state["current_announcement"] = {
            "id": announcement["id"], "description": announcement["description"], "mode": mode,
        }
        self.state["tracks_since_announcement"] = 0
        self._deferred_advance_pending = deferred_advance
        self.state["state"] = "announcing"
        await self._emit("radio_play_announcement", client_ts)

    async def announcement_ended(self, client_ts: float | None = None):
        """Fin de rappel rapportée par le lecteur /radio. En mode « wait_end »,
        l'avancement à la piste suivante — différé depuis la fin de piste
        précédente — a enfin lieu ici."""
        self.state["current_announcement"] = None
        if self._deferred_advance_pending:
            self._deferred_advance_pending = False
            await self._advance_or_stop(client_ts)
        else:
            self.state["state"] = "playing" if self.state["playing"] else "paused"
            await self._emit("radio_announcement_ended", client_ts)

    async def seek(self, position_seconds: float, client_ts: float | None = None):
        self.state["position_seconds"] = max(0.0, position_seconds)
        if self.state["current_track"] is not None:
            self._clock.seek(self.state["position_seconds"], lead_ms=self._lead_ms(PLAY_LEAD_MS) if self._clock.running else 0.0)
        await self._emit("radio_seek", client_ts)

    async def set_volume(self, volume: float, client_ts: float | None = None):
        self.state["volume"] = max(0, min(100, int(volume)))
        await self._emit("radio_volume", client_ts)

    async def set_sound(self, sound: dict, client_ts: float | None = None):
        """Applique des réglages de son DÉJÀ validés (cf. utils/radio_sound.py) et les
        diffuse : le moteur reste sans accès à la base, la persistance est faite par
        l'appelant."""
        self.state["sound"] = sound
        await self._emit("radio_sound_change", client_ts)

    async def set_mix(self, mix: dict, client_ts: float | None = None):
        """Applique une table de mixage DÉJÀ validée (cf. utils/radio_mix.py) et la diffuse ; persistance par l'appelant."""
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

    async def set_shuffle(self, on: bool, client_ts: float | None = None):
        self.state["shuffle"] = bool(on)
        order = self.state["order"]
        idx = self.state["index"]
        # Ne réordonne que les pistes À VENIR (garde l'historique et la piste
        # courante en place). Désactiver le shuffle ne restaure pas l'ordre
        # d'origine (recharger la playlist pour cela) — limitation assumée en L3.
        if on and order and idx is not None and idx + 1 < len(order):
            upcoming = order[idx + 1:]
            random.shuffle(upcoming)
            self.state["order"] = order[: idx + 1] + upcoming
        await self._emit("radio_set_shuffle", client_ts)

    async def set_repeat(self, mode: str, client_ts: float | None = None):
        if mode not in REPEAT_MODES:
            return
        self.state["repeat"] = mode
        await self._emit("radio_set_repeat", client_ts)

    async def add_to_queue(self, track: dict, client_ts: float | None = None):
        """Ajoute une piste en FIN de file d'attente. Voir `play_next` pour
        l'insertion immédiate après la piste en cours."""
        order = self.state["order"]
        order.append(track)
        self.state["order"] = order
        # Si rien ne jouait, cette piste devient la piste courante.
        if self.state["index"] is None:
            self.state["index"] = len(order) - 1
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def play_next(self, track: dict, client_ts: float | None = None):
        """« Lire ensuite » : insère une piste juste après la piste courante,
        devant tout ce qui est déjà en file d'attente."""
        order = self.state["order"]
        idx = self.state["index"]
        insert_at = (idx + 1) if idx is not None else len(order)
        order.insert(insert_at, track)
        self.state["order"] = order
        if self.state["index"] is None:
            self.state["index"] = insert_at
            self._sync_current()
        await self._emit("radio_queue_changed", client_ts)

    async def move_in_order(self, from_index: int, to_index: int, client_ts: float | None = None):
        """Déplace une piste de la file « À suivre » (glisser-déposer de l'admin).

        Seules les pistes À VENIR (après la piste courante) peuvent bouger : l'historique et la
        piste en cours restent en place, sinon la lecture changerait de piste sous les pieds de
        l'auditoire. Indices hors file ou identiques : sans effet (pas d'évènement inutile).
        `to_index` est borné à la file."""
        order = self.state["order"]
        cur = self.state["index"]
        if cur is None or not order:
            return
        first = cur + 1
        if not (first <= from_index < len(order)):
            return
        target = max(first, min(to_index, len(order) - 1))
        if target == from_index:
            return
        order.insert(target, order.pop(from_index))
        self.state["order"] = order
        await self._emit("radio_queue_changed", client_ts)

    async def remove_from_order(self, index: int, client_ts: float | None = None):
        """Retire une piste de l'ordre de lecture (file d'attente)."""
        order = self.state["order"]
        if not (0 <= index < len(order)):
            return
        cur = self.state["index"] or 0
        order.pop(index)
        if index < cur:
            self.state["index"] = cur - 1
        elif index == cur:
            # La piste courante a été retirée : on reste sur le même index
            # (= piste suivante) en le bornant à la fin de liste.
            self.state["index"] = min(cur, len(order) - 1) if order else None
        self.state["order"] = order
        if not order:
            self.state.update({"playing": False, "state": "idle"})
            self._clock.reset()
        self._sync_current()
        if index == cur and order:
            # La piste courante a été retirée : la suivante démarre de zéro.
            self.state["position_seconds"] = 0.0
            if self.state["playing"]:
                self._start_clock(0.0)
            else:
                self._clock.reset()
        await self._emit("radio_queue_changed", client_ts)

    async def report_position(self, position_seconds: float):
        """Rapport de position du lecteur /radio (pas de diffusion à chaque
        appel — la boucle de position s'en charge)."""
        # La position vient de l'horloge serveur ; ce rapport ne la
        # modifie plus (diagnostic seulement).
        self._last_direct_report = time.monotonic()


_managers: dict[str, RadioPlaybackManager] = {}


def init_radio_managers(broadcast: BroadcastFn) -> dict[str, RadioPlaybackManager]:
    """Crée les deux moteurs radio, un par sortie."""
    global _managers
    _managers = {channel: RadioPlaybackManager(broadcast, channel) for channel in RADIO_CHANNELS}
    return _managers


def get_radio_manager(channel: str | None = None) -> RadioPlaybackManager:
    """Moteur de la sortie demandée (alias historique accepté ; défaut : réseau)."""
    manager = _managers.get(normalize_radio_channel(channel))
    if manager is None:
        raise RuntimeError("RadioPlaybackManager non initialisé")
    return manager


def get_all_radio_managers() -> dict[str, RadioPlaybackManager]:
    return dict(_managers)

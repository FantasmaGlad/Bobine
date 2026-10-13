"""Horloge de lecture vidéo pilotée par le SERVEUR (réf. plan 4.0, lot P2-2).

Pourquoi : jusqu'ici la position d'un cours n'existait que si un kiosque
« primaire » la rapportait (≤ 1 fois/s) — sans kiosque connecté sur le canal,
le cours était « en lecture » mais n'avançait jamais, et chaque écran miroir
se recalait par `seek` sur une position déjà âgée (donc gelait). Avec une
horloge côté serveur, la position est une FONCTION DU TEMPS :

    position(t) = position_ancre + (t - instant_ancre) * vitesse     (si en lecture)

Chaque écran la recalcule localement (et corrige sa dérive en ajustant
`playbackRate`, sans `seek`) : plus aucun tick fréquent à diffuser, plus de
dépendance à un primaire, et un démarrage simultané possible grâce à un
instant de départ futur (`lead_ms`).

Module PUR (aucune E/S, horloges injectables) pour rester testable. Deux
horloges sont utilisées volontairement :
  * `monotonic` pour faire avancer la position côté serveur (insensible à un
    saut NTP de l'heure murale) ;
  * `epoch_ms` (heure murale) uniquement pour DATER les ancres transmises aux
    clients, qui la comparent à leur propre décalage d'horloge (`/api/time`).
"""

from __future__ import annotations

import time
from typing import Callable


class PlaybackClock:
    def __init__(
        self,
        monotonic: Callable[[], float] = time.monotonic,
        epoch_ms: Callable[[], float] = lambda: time.time() * 1000.0,
    ) -> None:
        self._monotonic = monotonic
        self._epoch_ms = epoch_ms
        self._position = 0.0
        self._rate = 1.0
        self._running = False
        # Compteur incrémenté à chaque DISCONTINUITÉ voulue (démarrage, pause,
        # seek, changement de vitesse, arrêt) : permet à un écran de distinguer
        # un ORDRE explicite (à appliquer tout de suite, sans délai de grâce ni
        # anti-boucle) d'une simple dérive à corriger en douceur.
        self._epoch = 0
        # Instant (monotonic) à partir duquel la position commence à avancer.
        # Peut être dans le futur (démarrage synchronisé, cf. `lead_ms`).
        self._start_mono = 0.0

    # ------------------------------------------------------------------
    # Lecture de l'état
    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self._running

    @property
    def rate(self) -> float:
        return self._rate

    def position(self) -> float:
        """Position courante en secondes (jamais négative)."""
        if not self._running:
            return self._position
        elapsed = self._monotonic() - self._start_mono
        if elapsed <= 0.0:
            return self._position
        return self._position + elapsed * self._rate

    def to_dict(self) -> dict:
        """Ancre transmise aux clients : « à l'instant serveur `at_ms`
        (epoch, ms), la position était `pos` ; si `running`, elle avance à
        `rate` depuis cet instant ».

        Recalculée à chaque émission (donc ré-ancrée sur « maintenant » à
        chaque heartbeat) — un client n'accumule jamais d'erreur d'extrapolation
        sur une longue durée. Si le départ est encore dans le futur, l'ancre
        est l'instant de départ lui-même, ce qui permet à chaque écran de
        démarrer exactement au même moment.
        """
        now_mono = self._monotonic()
        now_ms = self._epoch_ms()
        if self._running and self._start_mono > now_mono:
            at_ms = now_ms + (self._start_mono - now_mono) * 1000.0
            pos = self._position
        else:
            at_ms = now_ms
            pos = self.position()
        return {
            "pos": round(pos, 3),
            "at_ms": int(round(at_ms)),
            "rate": self._rate,
            "running": self._running,
            "epoch": self._epoch,
        }

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------
    def start(self, position: float | None = None, lead_ms: float = 0.0) -> None:
        """(Re)démarre la lecture depuis `position` (défaut : position
        courante), dans `lead_ms` millisecondes."""
        base = self.position() if position is None else max(0.0, position)
        self._epoch += 1
        self._position = base
        self._running = True
        self._start_mono = self._monotonic() + max(0.0, lead_ms) / 1000.0

    def pause(self) -> None:
        """Fige la position courante."""
        self._epoch += 1
        self._position = self.position()
        self._running = False

    def seek(self, position: float, lead_ms: float = 0.0) -> None:
        """Déplace la position ; conserve l'état en lecture/pause."""
        self._epoch += 1
        self._position = max(0.0, position)
        if self._running:
            self._start_mono = self._monotonic() + max(0.0, lead_ms) / 1000.0

    def set_rate(self, rate: float) -> None:
        """Change la vitesse SANS saut de position."""
        self._epoch += 1
        self._position = self.position()
        self._rate = float(rate)
        if self._running:
            self._start_mono = self._monotonic()

    def reset(self) -> None:
        """Arrêt complet (aucun cours) : position 0, à l'arrêt. La vitesse
        choisie est conservée (réglage de l'utilisateur, pas de la lecture)."""
        self._epoch += 1
        self._position = 0.0
        self._running = False
        self._start_mono = 0.0

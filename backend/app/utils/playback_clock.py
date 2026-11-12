"""Horloge de lecture vidéo pilotée par le SERVEUR."""

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
        self._epoch = 0
        self._start_mono = 0.0

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
        """Ancre transmise aux clients : « à l'instant serveur `at_ms` (epoch, ms), la position était `pos` ; si `running`, elle avance à `rate` depuis cet instant »."""
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

    def start(self, position: float | None = None, lead_ms: float = 0.0) -> None:
        """(Re)démarre la lecture depuis `position` (défaut : position courante), dans `lead_ms` millisecondes."""
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
        """Arrêt complet (aucun cours) : position 0, à l'arrêt."""
        self._epoch += 1
        self._position = 0.0
        self._running = False
        self._start_mono = 0.0

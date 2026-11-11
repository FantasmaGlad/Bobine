"""Position de reprise d'une programmation interrompue par un arrêt du serveur.

Fonctions pures : un cours programmé suit l'heure murale de son lancement, pas le temps réellement joué. Un
redémarrage à 18 h 14 d'un cours lancé à 18 h 00 le reprend donc à la quatorzième minute.
"""
from __future__ import annotations

from datetime import datetime

# En dessous de ce reste, reprendre n'afficherait que la fin du cours : on ne relance pas.
MIN_REMAINING_SECONDS = 20.0


def playback_offset(started_at: datetime, now: datetime, duration_seconds: float | None) -> float | None:
    """Position (en secondes) où reprendre un média lancé à `started_at`, ou `None` s'il n'y a plus rien à jouer.

    `None` aussi quand la durée est inconnue ou que `now` précède le lancement (horloge système fausse)."""
    if not duration_seconds or duration_seconds <= 0:
        return None
    elapsed = (now - started_at).total_seconds()
    if elapsed < 0 or elapsed > duration_seconds - MIN_REMAINING_SECONDS:
        return None
    return elapsed


def playlist_resume_point(
    durations: list[float | None], gap_seconds: float, elapsed: float
) -> tuple[int, float] | None:
    """Vidéo et position où reprendre une playlist lancée depuis `elapsed` secondes, ou `None` si elle est finie.

    `gap_seconds` est l'attente entre deux cours. Une reprise qui tombe dans une attente, ou dans les dernières
    secondes d'une vidéo, démarre la vidéo suivante à zéro. Une durée inconnue rend le calcul impossible."""
    if elapsed < 0:
        return None
    for index, duration in enumerate(durations):
        if not duration or duration <= 0:
            return None
        has_next = index + 1 < len(durations)
        if elapsed <= duration - MIN_REMAINING_SECONDS:
            return index, elapsed
        if elapsed < duration + gap_seconds:
            return (index + 1, 0.0) if has_next else None
        elapsed -= duration + gap_seconds
    return None

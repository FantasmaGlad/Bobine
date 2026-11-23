"""Disposition de la mosaïque d'aperçu d'une vidéo : calcul pur, partagé par la génération et l'API."""
from __future__ import annotations

import math
from dataclasses import dataclass

MIN_INTERVAL_SECONDS = 10
MAX_TILES = 240
COLUMNS = 10
TILE_WIDTH = 160
TILE_HEIGHT = 90


@dataclass(frozen=True)
class StoryboardLayout:
    interval_seconds: int
    count: int
    columns: int
    rows: int
    tile_width: int
    tile_height: int


def storyboard_layout(duration_seconds: float | None) -> StoryboardLayout | None:
    """Une vignette toutes les 10 s au moins, 240 au plus ; None sans durée connue."""
    if not duration_seconds or duration_seconds <= 0:
        return None
    interval = max(MIN_INTERVAL_SECONDS, math.ceil(duration_seconds / MAX_TILES))
    count = max(1, math.ceil(duration_seconds / interval))
    columns = min(COLUMNS, count)
    return StoryboardLayout(interval, count, columns, math.ceil(count / columns), TILE_WIDTH, TILE_HEIGHT)

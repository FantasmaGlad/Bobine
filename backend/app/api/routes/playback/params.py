"""Paramètres numériques exigés par les commandes de lecture, vérifiés avant toute action."""

import math
from typing import Any

from .core import CommandRejected

REQUIRED_NUMBERS: dict[str, str] = {
    "seek": "position_seconds",
    "report_position": "position_seconds",
    "volume": "volume",
    "speed": "speed",
    "audio_jump_to_track": "index",
    "audio_report_position": "position_seconds",
    "audio_set_chain_timer": "seconds",
    "radio_jump_to_track": "index",
    "radio_seek": "position_seconds",
    "radio_remove_from_queue": "index",
}


def require_numbers(command: str | None, params: dict[str, Any], channel: str) -> None:
    key = REQUIRED_NUMBERS.get(command or "")
    if key is None:
        return
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise CommandRejected("invalid_params", channel, f"{command} : paramètre `{key}` attendu, nombre positif ou nul.", 422)

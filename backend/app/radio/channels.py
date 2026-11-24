"""Sorties radio : identifiants canoniques et cibles des règles de rappel."""

from __future__ import annotations

from typing import Any

from app.api.contract import RADIO_CHANNELS
from app.outputs import DEFAULT_RADIO_CHANNEL


def normalize_radio_channel(value: Any) -> str:
    """Identifiant de sortie radio canonique ; toute valeur absente ou inconnue retombe sur la radio par défaut."""
    if value in RADIO_CHANNELS:
        return value
    return DEFAULT_RADIO_CHANNEL


def rule_targets_output(target: Any, radio_channel: str) -> bool:
    """Vrai si une règle de rappel de cible `target` s'applique à la sortie `radio_channel`."""
    return normalize_radio_channel(target) == normalize_radio_channel(radio_channel)


def is_radio_channel(value: Any) -> bool:
    """Vrai pour un identifiant de sortie radio."""
    return value in RADIO_CHANNELS

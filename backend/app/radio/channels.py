"""Sorties radio : identifiants canoniques et cibles des règles de rappel."""

from __future__ import annotations

from typing import Any

from app.api.contract import LEGACY_RADIO_CHANNEL, RADIO_CHANNELS

DEFAULT_RADIO_CHANNEL = "radio_network"


def normalize_radio_channel(value: Any) -> str:
    """Identifiant de sortie radio canonique : l'alias historique `radio` devient `radio_network` ; toute valeur absente ou inconnue retombe sur le défaut."""
    if value in RADIO_CHANNELS:
        return value
    return DEFAULT_RADIO_CHANNEL


RULE_TARGET_BOTH = "both"


RULE_TARGETS = (*RADIO_CHANNELS, RULE_TARGET_BOTH)


def normalize_rule_target(value: Any) -> str:
    """Cible d'une règle de rappel."""
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

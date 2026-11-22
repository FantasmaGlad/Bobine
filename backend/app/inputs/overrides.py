"""Réglage des entrées : validation et fusion des correspondances choisies avec la table par défaut."""

from __future__ import annotations

import re

from app.inputs.bindings import DEFAULT_BINDINGS, REMOTE_ACTIONS

MAX_OVERRIDES = 64
MAX_CHAIN = 3
INPUT_PATTERN = re.compile(r"^(?:key:[^\x00-\x1f\x7f]{1,32}|code:[0-9]{1,3}|pad:(?:[0-9]|1[0-9]))$")

Overrides = dict[str, tuple[str, ...]]


def check_input(source: str) -> str:
    if not isinstance(source, str) or not INPUT_PATTERN.match(source):
        raise ValueError("entrée invalide : key:<touche>, code:<0-999> ou pad:<0-19>")
    return source


def check_actions(actions: object) -> tuple[str, ...]:
    if not isinstance(actions, (list, tuple)) or len(actions) > MAX_CHAIN:
        raise ValueError(f"actions : liste de {MAX_CHAIN} actions au plus")
    unknown = [action for action in actions if action not in REMOTE_ACTIONS]
    if unknown:
        raise ValueError(f"action inconnue : {', '.join(map(str, unknown))}")
    if len(set(actions)) != len(actions):
        raise ValueError("actions : une action ne se répète pas")
    return tuple(actions)


def parse_overrides(raw: object) -> Overrides:
    """Relit les correspondances stockées ; une valeur abîmée est refusée en entier."""
    if not isinstance(raw, dict) or len(raw) > MAX_OVERRIDES:
        raise ValueError(f"correspondances : objet de {MAX_OVERRIDES} entrées au plus")
    return {check_input(source): check_actions(actions) for source, actions in raw.items()}


def with_override(overrides: Overrides, source: str, actions: object | None) -> Overrides:
    """`actions` vide désactive l'entrée, `None` rend la valeur par défaut."""
    updated = dict(overrides)
    if actions is None:
        updated.pop(check_input(source), None)
        return updated
    updated[check_input(source)] = check_actions(actions)
    if len(updated) > MAX_OVERRIDES:
        raise ValueError(f"au plus {MAX_OVERRIDES} correspondances personnalisées")
    return updated


def effective_bindings(overrides: Overrides) -> dict[str, list[str]]:
    merged = {**DEFAULT_BINDINGS, **overrides}
    return {source: list(actions) for source, actions in merged.items() if actions}

"""Planning exporté avant la ligne unique par sortie : chaque fichier d'une voie radio rejoint celui de sa sortie."""
from __future__ import annotations

from typing import Any

from app import config_files

_PREFIXES = ("schedule/radio-", "schedule-radio-")


def _lane(name: str) -> str | None:
    for prefix in _PREFIXES:
        if name.startswith(prefix) and name.endswith(".json"):
            return name[len(prefix):-len(".json")]
    return None


def _output_of(lane: str, recent: bool) -> str | None:
    """`network` désignait la radio réseau, devenue celle de Réseau 2 ; un export récent (avec `network-2`) l'a déjà séparée."""
    if lane == "network":
        return "network" if recent else "network_2"
    return {"cable": "cable", "network-2": "network_2"}.get(lane)


def merge_radio_schedules(files: dict[str, Any]) -> dict[str, Any]:
    lanes = {name: lane for name in files if (lane := _lane(name))}
    if not lanes:
        return files
    recent = "network-2" in lanes.values()
    merged = {name: document for name, document in files.items() if name not in lanes}
    for name, lane in lanes.items():
        output = _output_of(lane, recent)
        if output is None:
            merged[name] = files[name]
            continue
        target = config_files.schedule_path(output)
        base = merged.get(target) or {"schema": config_files.SCHEMA, "kind": config_files.KINDS[target], "channel": output, "schedules": []}
        legacy = files[name] if isinstance(files[name], dict) else {}
        merged[target] = {**base, "schedules": [*(base.get("schedules") or []), *(legacy.get("schedules") or [])]}
    return merged

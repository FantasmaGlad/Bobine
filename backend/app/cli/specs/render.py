from __future__ import annotations

import math
from typing import Any

LABELS = ("title", "name", "label", "description", "address", "alias", "key", "event_type", "message")


class _Blank(dict):
    def __missing__(self, key: str) -> str:
        return "-"


def lines(template: str):
    return lambda payload, args: "\n".join(template.format_map(_Blank(item)) for item in (payload or []) if isinstance(item, dict))


def _label(item: dict) -> str:
    return next((str(item[key]) for key in LABELS if item.get(key) not in (None, "")), "")


def _row(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    ident = item.get("id", item.get("key", ""))
    return f"{ident}  {_label(item)}".strip()


def _items(payload: Any) -> list | None:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return next((payload[key] for key in ("items", "entries", "results") if isinstance(payload.get(key), list)), None)
    return None


MISSING = "—"


def value_text(value: Any) -> str:
    if value is None or value == "":
        return MISSING
    if isinstance(value, bool):
        return "oui" if value else "non"
    return str(value)


def minutes(seconds: Any) -> str:
    """Durée arrondie à la minute la plus proche, comme l'interface (`formatMinutes`)."""
    return f"{math.floor(seconds / 60 + 0.5)} min" if isinstance(seconds, (int, float)) and seconds > 0 else "-"


def _field_lines(payload: dict, indent: str, depth: int) -> list[str]:
    out: list[str] = []
    for key, value in payload.items():
        if isinstance(value, dict) and value and depth < 3:
            out.append(f"{indent}{key} :")
            out.extend(_field_lines(value, indent + "  ", depth + 1))
        elif isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            out.append(f"{indent}{key} ({len(value)}) :")
            out.extend(f"{indent}  {_row(item) or ', '.join(f'{k}={value_text(v)}' for k, v in item.items())}" for item in value)
        elif isinstance(value, list):
            out.append(f"{indent}{key} : {', '.join(value_text(item) for item in value) or MISSING}")
        else:
            out.append(f"{indent}{key} : {value_text(value)}")
    return out


def describe(payload: Any, args: Any = None) -> str:
    """Affichage d'une lecture : liste ou ligne d'identification, sinon le détail des champs."""
    if isinstance(payload, dict) and _items(payload) is None and not _row(payload):
        return "\n".join(_field_lines(payload, "", 0)) or "(vide)"
    return summary(payload, args)


def summary(payload: Any, args: Any = None) -> str:
    items = _items(payload)
    if items is not None:
        return "\n".join(_row(item) for item in items) or "(vide)"
    if isinstance(payload, dict):
        return _row(payload) or "Fait."
    return "Fait." if payload is None else str(payload)

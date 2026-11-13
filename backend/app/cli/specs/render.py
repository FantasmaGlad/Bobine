from __future__ import annotations

from typing import Any

LABELS = ("title", "name", "label", "description", "ssid", "address", "alias", "key", "event_type", "message")


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


def summary(payload: Any, args: Any = None) -> str:
    items = _items(payload)
    if items is not None:
        return "\n".join(_row(item) for item in items) or "(vide)"
    if isinstance(payload, dict):
        return _row(payload) or "Fait."
    return "Fait." if payload is None else str(payload)

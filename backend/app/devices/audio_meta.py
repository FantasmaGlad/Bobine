"""Nom personnalisé et masquage des sorties audio : réglage de Bobine commun à toutes les plateformes."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Setting

from .base import DeviceError

AUDIO_META_KEY = "devices_audio_meta"
_AUDIO_META_MAX = 200
_ALIAS_MAX = 60


def _read(db: Session) -> str | None:
    row = db.query(Setting).filter(Setting.key == AUDIO_META_KEY).first()
    return row.value if row else None


def _write(db: Session, value: str | None) -> None:
    row = db.query(Setting).filter(Setting.key == AUDIO_META_KEY).first()
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Setting(key=AUDIO_META_KEY, value=value))
    else:
        row.value = value
    db.commit()


def load_audio_meta(db: Session) -> dict[str, dict[str, Any]]:
    raw = _read(db)
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def with_meta(entry: dict[str, Any], meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    info = meta.get(str(entry.get("id")), {})
    return {**entry, "alias": info.get("alias") or None, "hidden": bool(info.get("hidden"))}


def with_listing_meta(listing: dict[str, Any] | None, db: Session) -> dict[str, Any] | None:
    if not listing or not listing.get("supported"):
        return listing
    meta = load_audio_meta(db)
    return {**listing, "devices": [with_meta(d, meta) for d in listing.get("devices", [])]}


def _apply_alias(entry: dict[str, Any], alias: str) -> None:
    alias = alias.strip()
    if len(alias) > _ALIAS_MAX or any(ord(c) < 32 for c in alias):
        raise DeviceError("bad_alias", f"Le nom doit faire au plus {_ALIAS_MAX} caractères, sans caractère de contrôle.", 400)
    if alias:
        entry["alias"] = alias
    else:
        entry.pop("alias", None)


def update_audio_meta(db: Session, sink_id: str, alias: str | None, hidden: bool | None) -> dict[str, Any]:
    if not sink_id or len(sink_id) > 256:
        raise DeviceError("bad_id", "Identifiant de sortie invalide.", 400)
    meta = load_audio_meta(db)
    entry = dict(meta.get(sink_id, {}))
    if alias is not None:
        _apply_alias(entry, alias)
    if hidden is not None:
        if hidden:
            entry["hidden"] = True
        else:
            entry.pop("hidden", None)
    if entry:
        if sink_id not in meta and len(meta) >= _AUDIO_META_MAX:
            raise DeviceError("too_many", "Trop de sorties personnalisées.", 400)
        meta[sink_id] = entry
    else:
        meta.pop(sink_id, None)
    _write(db, json.dumps(meta, ensure_ascii=False) if meta else None)
    return entry

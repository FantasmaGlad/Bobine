"""Boucles de visuels par canal, stockées dans les réglages `signage_<canal>`."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.models import Setting
from app.signage.playlist import SignageItem, parse_items, serialize

logger = logging.getLogger(__name__)


def _key(channel: str) -> str:
    return f"signage_{channel}"


def load(db: Session, channel: str) -> tuple[SignageItem, ...]:
    row = db.query(Setting).filter(Setting.key == _key(channel)).first()
    if row is None or not row.value:
        return ()
    try:
        return parse_items(json.loads(row.value))
    except ValueError as exc:
        logger.warning("Boucle de visuels du canal %s illisible, boucle vide appliquée : %s", channel, exc)
        return ()


def save(db: Session, channel: str, items: tuple[SignageItem, ...]) -> None:
    value = json.dumps(serialize(items))
    row = db.query(Setting).filter(Setting.key == _key(channel)).first()
    if row is None:
        db.add(Setting(key=_key(channel), value=value))
    else:
        row.value = value
    db.commit()

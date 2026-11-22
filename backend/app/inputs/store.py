"""Correspondances choisies, stockées dans le réglage `remote_bindings`."""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.inputs.overrides import Overrides, parse_overrides
from app.models import Setting

KEY = "remote_bindings"
logger = logging.getLogger(__name__)


def load(db: Session) -> Overrides:
    row = db.query(Setting).filter(Setting.key == KEY).first()
    if row is None or not row.value:
        return {}
    try:
        return parse_overrides(json.loads(row.value))
    except ValueError as exc:
        logger.warning("Correspondances des entrées illisibles, table par défaut appliquée : %s", exc)
        return {}


def save(db: Session, overrides: Overrides) -> None:
    value = json.dumps({source: list(actions) for source, actions in overrides.items()}, ensure_ascii=False)
    row = db.query(Setting).filter(Setting.key == KEY).first()
    if row is None:
        db.add(Setting(key=KEY, value=value))
    else:
        row.value = value
    db.commit()

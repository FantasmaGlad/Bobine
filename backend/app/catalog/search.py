from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.catalog import query
from app.catalog.entries import Entry, LOADERS


def _entries(db: Session, keys: list[tuple[str, int]]) -> list[Entry]:
    ids: dict[str, list[int]] = defaultdict(list)
    for kind, ident in keys:
        ids[kind].append(ident)
    loaded = {(e.kind, e.id): e for kind, group in ids.items() for e in LOADERS[kind](db, group)}
    return [loaded[key] for key in keys if key in loaded]


def catalog(db: Session, kinds: tuple[str, ...], text: str | None, limit: int, offset: int) -> tuple[list[Entry], int]:
    keys = [(row.kind, row.id) for row in db.execute(query.page(kinds, text, limit, offset))]
    return _entries(db, keys), db.execute(query.total(kinds, text)).scalar_one()

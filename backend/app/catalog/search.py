from __future__ import annotations

import unicodedata

from app.catalog.entries import Entry, LOADERS


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def matches(entry: Entry, query: str | None) -> bool:
    haystack = f"{_fold(entry.title)} {_fold(entry.subtitle)} {entry.id}"
    return all(word in haystack for word in _fold(query).split())


def catalog(db, kinds: tuple[str, ...], query: str | None) -> list[Entry]:
    entries = [entry for kind in kinds for entry in LOADERS[kind](db) if matches(entry, query)]
    return sorted(entries, key=lambda e: (kinds.index(e.kind), _fold(e.title), e.id))

from __future__ import annotations

from sqlalchemy import String, cast, func, literal, select, union_all

from app.catalog.fold import fold
from app.models import AudioCourse, AudioPlaylist, Background, Playlist, RadioPlaylist, RadioTrack, Video

SOURCES = {
    "video": (Video, Video.title, Video.program),
    "playlist": (Playlist, Playlist.name, None),
    "audio": (AudioCourse, AudioCourse.title, AudioCourse.program),
    "audio-playlist": (AudioPlaylist, AudioPlaylist.name, None),
    "background": (Background, Background.title, None),
    "radio-track": (RadioTrack, RadioTrack.title, RadioTrack.artist),
    "radio-playlist": (RadioPlaylist, RadioPlaylist.name, None),
}


def _folded(column):
    return func.bobine_fold(column, type_=String)


def _source(rank: int, kind: str, words: list[str]):
    model, title, secondary = SOURCES[kind]
    haystack = _folded(title) + " " + _folded(func.coalesce(secondary, "")) + " " + cast(model.id, String)
    statement = select(literal(rank).label("rank"), literal(kind).label("kind"), model.id.label("id"),
                       _folded(title).label("sort"))
    return statement.where(*(func.instr(haystack, word) > 0 for word in words))


def matching(kinds: tuple[str, ...], query: str | None):
    words = fold(query).split()
    return union_all(*(_source(rank, kind, words) for rank, kind in enumerate(kinds))).subquery()


def page(kinds: tuple[str, ...], query: str | None, limit: int, offset: int):
    rows = matching(kinds, query)
    return select(rows.c.kind, rows.c.id).order_by(rows.c.rank, rows.c.sort, rows.c.id).limit(limit).offset(offset)


def total(kinds: tuple[str, ...], query: str | None):
    return select(func.count()).select_from(matching(kinds, query))

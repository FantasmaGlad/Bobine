from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from sqlalchemy.orm import Session, selectinload

from app.models import AudioCourse, AudioPlaylist, AudioPlaylistItem, Background, Playlist, PlaylistItem, RadioPlaylist, RadioPlaylistItem, RadioTrack, Video


@dataclass(frozen=True)
class Entry:
    kind: str
    id: int
    title: str
    subtitle: str | None
    duration_seconds: float | None
    available: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _sum(values) -> float | None:
    total = sum(value or 0.0 for value in values)
    return total or None


def _videos(db: Session) -> list[Entry]:
    return [Entry("video", v.id, v.title, v.program, v.duration_seconds, v.available) for v in db.query(Video).all()]


def _playlists(db: Session) -> list[Entry]:
    rows = db.query(Playlist).options(selectinload(Playlist.items).joinedload(PlaylistItem.video)).all()
    return [Entry("playlist", p.id, p.name, f"{len(p.items)} vidéo(s)", _sum(i.video.duration_seconds for i in p.items if i.video),
                  any(i.video and i.video.available for i in p.items)) for p in rows]


def _audio(db: Session) -> list[Entry]:
    rows = db.query(AudioCourse).options(selectinload(AudioCourse.tracks)).all()
    return [Entry("audio", c.id, c.title, c.program, _sum(t.duration_seconds for t in c.tracks), c.available) for c in rows]


def _audio_playlists(db: Session) -> list[Entry]:
    rows = db.query(AudioPlaylist).options(selectinload(AudioPlaylist.items).joinedload(AudioPlaylistItem.track)).all()
    return [Entry("audio-playlist", p.id, p.name, f"{len(p.items)} piste(s)", _sum(i.track.duration_seconds for i in p.items if i.track),
                  any(i.track and i.track.available for i in p.items)) for p in rows]


def _backgrounds(db: Session) -> list[Entry]:
    return [Entry("background", b.id, b.title, "image" if b.is_image else "vidéo", b.duration_seconds, True)
            for b in db.query(Background).all()]


def _radio_tracks(db: Session) -> list[Entry]:
    return [Entry("radio-track", t.id, t.title, t.artist, t.duration_seconds, t.available) for t in db.query(RadioTrack).all()]


def _radio_playlists(db: Session) -> list[Entry]:
    rows = db.query(RadioPlaylist).options(selectinload(RadioPlaylist.items).joinedload(RadioPlaylistItem.track)).all()
    return [Entry("radio-playlist", p.id, p.name, "ambiance par défaut" if p.is_default else f"{len(p.items)} morceau(x)",
                  _sum(i.track.duration_seconds for i in p.items if i.track), bool(p.items)) for p in rows]


LOADERS: dict[str, Callable[[Session], list[Entry]]] = {
    "video": _videos,
    "playlist": _playlists,
    "audio": _audio,
    "audio-playlist": _audio_playlists,
    "background": _backgrounds,
    "radio-track": _radio_tracks,
    "radio-playlist": _radio_playlists,
}

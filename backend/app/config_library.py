"""Fichiers de configuration des bibliothèques : vidéos, cours audio, pistes radio, fonds."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config_files import envelope, file_name
from app.models import (
    Background,
    RadioTrack,
    Video,
)


def _ordered(db: Session, model, *keys):
    return db.query(model).order_by(*keys, model.id).all()


def build_library_videos(db: Session) -> dict[str, Any]:
    videos = _ordered(db, Video, Video.title)
    return envelope("library-videos", {"videos": [_video_entry(v) for v in videos]})


def _linked_file(path: str | None) -> dict[str, str] | None:
    return {"file": Path(path).name, "path": path} if path else None


def _video_entry(v: Video) -> dict[str, Any]:
    subtitles = sorted(v.subtitles, key=lambda s: (s.language_code, s.id))
    return {
        "uid": v.uid, "title": v.title, "program": v.program, "release": v.release, "description": v.description,
        "file": file_name(v.file_path),
        "chapters": bool(v.chapters), "chapters_source": v.chapters_source if v.chapters else None,
        "chapters_file": _linked_file(v.chapters_file) if v.chapters else None,
        "subtitles": bool(subtitles),
        "subtitle_files": [
            {"language": s.language_code, "label": s.language_label, "format": s.format, **(_linked_file(s.file_path) or {})}
            for s in subtitles
        ],
    }


def build_library_audio(db: Session) -> dict[str, Any]:
    from app.models import AudioCourse

    courses = _ordered(db, AudioCourse, AudioCourse.title)
    return envelope("library-audio", {"courses": [{
        "uid": c.uid, "title": c.title, "program": c.program, "release": c.release,
        "tracks": [{"uid": t.uid, "number": t.number, "title": t.title, "file": file_name(t.file_path)}
                   for t in sorted(c.tracks, key=lambda t: (t.number or 0, t.id))],
    } for c in courses]})


def build_library_radio(db: Session) -> dict[str, Any]:
    tracks = _ordered(db, RadioTrack, RadioTrack.title)
    return envelope("library-radio", {"tracks": [{
        "uid": t.uid, "title": t.title, "artist": t.artist, "album": t.album, "album_artist": t.album_artist,
        "genre": t.genre, "track_number": t.track_number, "disc_number": t.disc_number, "year": t.year,
        "file": file_name(t.file_path),
    } for t in tracks]})


def build_library_backgrounds(db: Session) -> dict[str, Any]:
    backgrounds = _ordered(db, Background, Background.title)
    return envelope("library-backgrounds", {"backgrounds": [
        {"uid": b.uid, "title": b.title, "file": file_name(b.file_path)} for b in backgrounds]})

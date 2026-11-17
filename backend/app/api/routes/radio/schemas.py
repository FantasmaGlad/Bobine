"""Schémas de l'API de la bibliothèque musicale."""

from typing import List

from pydantic import BaseModel

from app.models import RadioTrack


class RadioTrackResponse(BaseModel):
    id: int
    title: str
    artist: str | None
    album: str | None
    album_artist: str | None
    track_number: int | None
    disc_number: int | None
    year: int | None
    genre: str | None
    duration_seconds: float | None
    has_cover: bool
    tags: List[str]
    available: bool = True
    external: bool = False


class RadioTrackUpdate(BaseModel):
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: int | None = None
    genre: str | None = None
    tags: List[str] | None = None


class TagInput(BaseModel):
    name: str


class ImportJobAccepted(BaseModel):
    job_id: str


def track_response(track: RadioTrack) -> dict:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "album_artist": track.album_artist,
        "track_number": track.track_number,
        "disc_number": track.disc_number,
        "year": track.year,
        "genre": track.genre,
        "duration_seconds": track.duration_seconds,
        "has_cover": track.cover_path is not None,
        "tags": sorted(t.name for t in track.tags),
        "available": track.available,
        "external": track.external,
    }

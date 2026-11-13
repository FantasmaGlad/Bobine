from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Response
from pydantic import BaseModel

from app.utils._pydantic_compat import OpenModel


class Message(BaseModel):
    message: str


class DeletedEntries(Message):
    deleted: int


class NextSchedule(BaseModel):
    run_at: str
    title: str


class RadioArtist(BaseModel):
    name: str
    track_count: int
    album_count: int


class RadioAlbum(BaseModel):
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_count: int
    year: Optional[int] = None
    cover_track_id: Optional[int] = None


class RadioTagEntry(BaseModel):
    id: int
    name: str


class RadioTagCount(RadioTagEntry):
    track_count: int


class RadioSound(OpenModel):
    enabled: bool
    bands: List[int]
    bass_boost: int
    loudness: bool
    limiter: bool
    preset: Optional[str] = None


class DefaultPlaylist(BaseModel):
    override_playlist_id: Optional[int] = None
    effective_playlist_id: Optional[int] = None


DefaultPlaylists = Dict[str, DefaultPlaylist]


class AnnouncementPlayed(BaseModel):
    id: int
    description: Optional[str] = None


class LaptopLid(BaseModel):
    has_lid: bool
    prevent_sleep: bool


class OpenedPath(BaseModel):
    status: str
    path: str
    message: Optional[str] = None


class CancelledJob(BaseModel):
    status: str
    job_id: str


class CourseRatingEntry(BaseModel):
    id: int
    video_id: int
    rating: int
    channel: Optional[str] = None
    source: Optional[str] = None
    created_at: str


class SessionStarted(BaseModel):
    session_id: int


class Health(BaseModel):
    status: str
    version: Optional[str] = None
    components: Dict[str, str]


class ServerTime(BaseModel):
    server_ts: int


class PlaybackSnapshot(OpenModel):
    state: str
    current_video: Any = None
    position_seconds: Any = None
    volume: Any = None
    speed: Any = None
    playlist_id: Any = None
    playlist_name: Any = None
    playlist_index: Any = None
    current_background: Any = None
    current_audio_course: Any = None
    audio_track_index: Any = None
    audio_playing: Any = None
    audio_position_seconds: Any = None
    scheduled_launch: Any = None
    clock: Any = None
    audio_clock: Any = None


class RadioSnapshot(OpenModel):
    state: str
    channel: str
    playlist_id: Any = None
    playlist_name: Any = None
    index: Any = None
    current_track: Any = None
    position_seconds: Any = None
    duration_seconds: Any = None
    volume: Any = None
    shuffle: Any = None
    repeat: Any = None
    playing: Any = None
    current_announcement: Any = None
    sound: Any = None
    clock: Any = None


class UploadState(BaseModel):
    upload_id: str
    offset: int
    size: int
    complete: bool
    chunk_size: int


def binary(*media_types: str) -> dict:
    return {"response_class": Response,
            "responses": {200: {"description": "Fichier", "content": {kind: {} for kind in media_types}}}}

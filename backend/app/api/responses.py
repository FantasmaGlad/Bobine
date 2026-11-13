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
    current_video: Optional[Dict[str, Any]] = None
    position_seconds: Optional[float] = None
    volume: Optional[int] = None
    speed: Optional[float] = None
    playlist_id: Optional[int] = None
    playlist_name: Optional[str] = None
    playlist_index: Optional[int] = None
    current_background: Optional[Dict[str, Any]] = None
    current_audio_course: Optional[Dict[str, Any]] = None
    audio_track_index: Optional[int] = None
    audio_playing: Optional[bool] = None
    audio_position_seconds: Optional[float] = None
    scheduled_launch: Optional[Dict[str, Any]] = None
    clock: Optional[Dict[str, Any]] = None
    audio_clock: Optional[Dict[str, Any]] = None


class RadioSnapshot(OpenModel):
    state: str
    channel: str
    playlist_id: Optional[int] = None
    playlist_name: Optional[str] = None
    index: Optional[int] = None
    current_track: Optional[Dict[str, Any]] = None
    position_seconds: Optional[float] = None
    duration_seconds: Optional[float] = None
    volume: Optional[int] = None
    shuffle: Optional[bool] = None
    repeat: Optional[Any] = None
    playing: Optional[bool] = None
    current_announcement: Optional[Dict[str, Any]] = None
    sound: Optional[Dict[str, Any]] = None
    clock: Optional[Dict[str, Any]] = None


class UploadState(BaseModel):
    upload_id: str
    offset: int
    size: int
    complete: bool
    chunk_size: int


def binary(*media_types: str) -> dict:
    return {"response_class": Response,
            "responses": {200: {"description": "Fichier", "content": {kind: {} for kind in media_types}}}}

"""Schémas de l'API des vidéos."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.models import VideoSubtitle
from app.utils._pydantic_compat import OrmModel


class VideoUpdate(BaseModel):
    title: str | None = None
    program: str | None = None
    release: str | None = None
    description: str | None = None


class VideoResponse(OrmModel):
    id: int
    file_path: str
    title: str
    program: str | None
    release: str | None
    duration_seconds: float | None
    width: int | None
    height: int | None
    codec: str | None
    thumbnail_path: str | None
    source: str
    description: str | None = None
    audio_channels: int | None = None
    audio_codec: str | None = None
    fps: float | None = None
    bitrate_kbps: int | None = None
    pix_fmt: str | None = None
    web_safe: bool = True
    web_issues: List[str] = []
    web_status: str | None = None
    available: bool = True
    external: bool = False


class VideoSubtitleResponse(OrmModel):
    id: int
    video_id: int
    language_code: str
    language_label: str
    format: str
    vtt_url: str


class ImportJobAccepted(BaseModel):
    job_id: str


def subtitle_response(sub: VideoSubtitle) -> VideoSubtitleResponse:
    return VideoSubtitleResponse(
        id=sub.id,
        video_id=sub.video_id,
        language_code=sub.language_code,
        language_label=sub.language_label,
        format=sub.format,
        vtt_url=f"/api/videos/{sub.video_id}/subtitles/{sub.id}/vtt",
    )

"""Schémas de l'API des cours audio."""

from typing import List

from pydantic import BaseModel

from app.models import AudioCourse
from app.utils._pydantic_compat import OrmModel


class AudioTrackResponse(OrmModel):
    id: int
    number: int | None
    title: str
    duration_seconds: float | None
    position: int
    background_id: int | None = None
    background_title: str | None = None
    background_is_image: bool = False
    available: bool = True
    external: bool = False


class AudioCourseResponse(OrmModel):
    id: int
    title: str
    program: str | None
    release: str | None
    background_id: int | None
    background_thumbnail_path: str | None = None
    track_count: int
    total_duration_seconds: float
    available: bool = True
    partially_available: bool = False
    external: bool = False


class AudioCourseDetailResponse(OrmModel):
    id: int
    title: str
    program: str | None
    release: str | None
    background_id: int | None
    tracks: List[AudioTrackResponse]


class AudioCourseUpdate(BaseModel):
    title: str | None = None
    program: str | None = None
    release: str | None = None
    background_id: int | None = None
    clear_background: bool = False


class TrackReorderInput(BaseModel):
    track_ids: List[int]


class AudioTrackWithCourseResponse(BaseModel):
    """Piste individuelle avec le contexte de son cours d'origine."""
    id: int
    number: int | None
    title: str
    duration_seconds: float | None
    course_id: int
    course_title: str
    course_program: str | None
    background_id: int | None = None
    background_title: str | None = None
    background_is_image: bool = False
    available: bool = True


class AudioTrackUpdate(BaseModel):
    title: str | None = None
    number: int | None = None
    background_id: int | None = None
    clear_background: bool = False


def summary(course: AudioCourse) -> dict:
    return {
        "id": course.id,
        "title": course.title,
        "program": course.program,
        "release": course.release,
        "background_id": course.background_id,
        "background_thumbnail_path": course.background_thumbnail_path,
        "track_count": len(course.tracks),
        "total_duration_seconds": sum(t.duration_seconds or 0.0 for t in course.tracks),
        "available": course.available,
        "partially_available": course.partially_available,
        "external": course.external,
    }


class ImportJobAccepted(BaseModel):
    job_id: str

"""Description des médias audio envoyée aux moteurs : cours audio et pistes."""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.models import AudioCourse, Background, Setting
from app.utils.importer.formats import is_image_background


def _background(db: Session, background_id: int | None) -> tuple[int | None, str | None, bool]:
    if not background_id:
        return background_id, None, False
    background = db.query(Background).filter(Background.id == background_id).first()
    if not background:
        return None, None, False
    return background_id, background.title, is_image_background(background.file_path)


def _default_background_id(db: Session) -> int | None:
    default_setting = db.query(Setting).filter(Setting.key == "default_coach_background_id").first()
    if default_setting and default_setting.value and default_setting.value.isdigit():
        return int(default_setting.value)
    return None


def _track_item(db: Session, track, course_background: tuple[int | None, str | None, bool]) -> dict:
    own = _background(db, getattr(track, "background_id", None))
    background_id, background_title, background_is_image = own if own[0] is not None else course_background
    return {
        "id": track.id,
        "number": track.number,
        "title": track.title,
        "duration_seconds": track.duration_seconds,
        "background_id": background_id,
        "background_title": background_title,
        "background_is_image": background_is_image,
    }


def _build_audio_course_item(course: AudioCourse, db: Session) -> dict:
    course_background = _background(db, course.background_id or _default_background_id(db))
    background_id, background_title, background_is_image = course_background
    tracks = [_track_item(db, t, course_background) for t in sorted(course.tracks, key=lambda t: t.position) if t.available]
    return {
        "id": course.id,
        "title": course.title,
        "program": course.program,
        "background_id": background_id,
        "background_title": background_title,
        "background_is_image": background_is_image,
        "tracks": tracks,
    }


def _build_audio_playlist_tracks(audio_playlist) -> list[dict]:
    sorted_items = sorted(audio_playlist.items, key=lambda item: item.position)
    return [
        {
            "id": item.track.id,
            "number": item.track.number,
            "title": item.track.title,
            "duration_seconds": item.track.duration_seconds,
            "background_id": item.background_id,
            "background_title": item.background.title if item.background else None,
            "background_is_image": is_image_background(item.background.file_path) if item.background else False,
        }
        for item in sorted_items
        if item.track.available
    ]


async def _load_audio_course_into_manager(course: AudioCourse, manager, db: Session, chain_mode=None, chain_timer_seconds=None, client_ts=None):
    item = await run_in_threadpool(_build_audio_course_item, course, db)
    await manager.load_audio_course(
        item["id"], item["title"], item["program"], item["background_id"], item["tracks"],
        chain_mode=chain_mode, chain_timer_seconds=chain_timer_seconds, client_ts=client_ts,
        background_title=item["background_title"], background_is_image=item["background_is_image"],
    )

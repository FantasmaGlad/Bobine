"""Commandes du mode coach : cours et playlists audio, pistes, enchaînement."""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.models import AudioCourse, AudioPlaylist, Background
from app.utils.activity_log import log_activity
from app.utils.importer.formats import is_image_background

from .context import Command
from .core import _reject_unavailable
from .media_items import _build_audio_playlist_tracks, _load_audio_course_into_manager


def _log_track_if_changed(db: Session, manager, index_before: int | None) -> None:
    index_after = manager.state.get("audio_track_index")
    if index_after is None or index_after == index_before:
        return
    tracks = manager.state.get("audio_tracks")
    if tracks and 0 <= index_after < len(tracks):
        log_activity(db, "audio_track_started", tracks[index_after]["title"])


async def _track_change(cmd: Command, move) -> None:
    index_before = cmd.manager.state.get("audio_track_index")
    await move()
    await run_in_threadpool(_log_track_if_changed, cmd.db, cmd.manager, index_before)


async def load_audio_course(cmd: Command) -> None:
    cmd.ensure_cable()
    await cmd.ensure_not_locked()
    course_id = cmd.params.get("audio_course_id")
    course = await cmd.fetch(AudioCourse, course_id)
    if not course:
        raise cmd.not_found(f"Cours audio {course_id}")
    if not await run_in_threadpool(lambda: course.available):
        await _reject_unavailable(cmd.name, cmd.channel, course.title, cmd.db)
    await _load_audio_course_into_manager(
        course, cmd.manager, cmd.db,
        chain_mode=cmd.params.get("chain_mode"),
        chain_timer_seconds=cmd.params.get("chain_timer_seconds"),
        client_ts=cmd.client_ts,
    )
    await cmd.log("audio_course_started", course.title)


async def load_audio_playlist(cmd: Command) -> None:
    cmd.ensure_cable()
    await cmd.ensure_not_locked()
    playlist_id = cmd.params.get("audio_playlist_id")
    playlist = await cmd.fetch(AudioPlaylist, playlist_id)
    if not playlist:
        raise cmd.not_found(f"Playlist audio {playlist_id}")
    tracks = await run_in_threadpool(_build_audio_playlist_tracks, playlist)
    await cmd.manager.load_audio_playlist(
        playlist.id, playlist.name, tracks,
        chain_mode=cmd.params.get("chain_mode"),
        chain_timer_seconds=cmd.params.get("chain_timer_seconds"),
        client_ts=cmd.client_ts,
    )
    log_activity(cmd.db, "audio_playlist_started", playlist.name)


async def audio_set_background(cmd: Command) -> None:
    background_id = cmd.params.get("background_id")
    title, is_image = None, False
    if background_id:
        background = cmd.db.query(Background).filter(Background.id == background_id).first()
        if not background:
            raise cmd.not_found(f"Fond animé {background_id}")
        title, is_image = background.title, is_image_background(background.file_path)
    await cmd.manager.audio_set_background(background_id, title, is_image, cmd.client_ts)


async def audio_next_track(cmd: Command) -> None:
    await _track_change(cmd, lambda: cmd.manager.audio_next_track(cmd.client_ts))


async def audio_previous_track(cmd: Command) -> None:
    await _track_change(cmd, lambda: cmd.manager.audio_previous_track(cmd.client_ts))


async def audio_jump_to_track(cmd: Command) -> None:
    index = int(cmd.params.get("index", 0))
    await _track_change(cmd, lambda: cmd.manager.audio_jump_to_track(index, cmd.client_ts))


async def audio_track_ended(cmd: Command) -> None:
    raw = cmd.params.get("track_index")
    track_index = raw if isinstance(raw, int) and not isinstance(raw, bool) else None
    await _track_change(cmd, lambda: cmd.manager.audio_track_ended(cmd.client_ts, track_index=track_index))


async def audio_report_position(cmd: Command) -> None:
    if not cmd.secondary_kiosk():
        await cmd.manager.audio_report_position(float(cmd.params.get("position_seconds", 0)))


HANDLERS = {
    "load_audio_course": load_audio_course,
    "load_audio_playlist": load_audio_playlist,
    "audio_set_background": audio_set_background,
    "audio_next_track": audio_next_track,
    "audio_previous_track": audio_previous_track,
    "audio_jump_to_track": audio_jump_to_track,
    "audio_track_ended": audio_track_ended,
    "audio_report_position": audio_report_position,
    "audio_restart_track": lambda cmd: cmd.manager.audio_restart_track(cmd.client_ts),
    "audio_set_chain_mode": lambda cmd: cmd.manager.audio_set_chain_mode(cmd.params.get("mode", "auto"), cmd.client_ts),
    "audio_set_chain_timer": lambda cmd: cmd.manager.audio_set_chain_timer(float(cmd.params.get("seconds", 20)), cmd.client_ts),
}

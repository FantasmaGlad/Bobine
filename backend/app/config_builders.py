"""Construction des fichiers de configuration depuis la base, un constructeur par famille."""

from __future__ import annotations

import json
from collections import Counter
from datetime import timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.api.contract import CHANNELS, SCHEDULE_CHANNELS
from app.config_files import PORTABLE_SETTINGS, envelope, file_name, schedule_path
from app.config_library import build_library_audio, build_library_backgrounds, build_library_radio, build_library_videos
from app.models import (
    AudioPlaylist,
    AudioTrack,
    Background,
    Playlist,
    RadioAnnouncement,
    RadioAnnouncementRule,
    RadioPlaylist,
    RadioTag,
    RadioTrack,
    Schedule,
    ScheduleTargetType,
    Video,
)


def video_ref(video: Video) -> dict[str, Any]:
    return {"uid": video.uid, "title": video.title, "program": video.program, "release": video.release, "file": file_name(video.file_path)}


def background_ref(background: Background | None) -> dict[str, Any] | None:
    if background is None:
        return None
    return {"uid": background.uid, "title": background.title, "file": file_name(background.file_path)}


def audio_track_ref(track: AudioTrack) -> dict[str, Any]:
    course = track.course
    return {
        "uid": track.uid,
        "course": {"uid": course.uid, "title": course.title, "program": course.program, "release": course.release},
        "number": track.number, "title": track.title, "file": file_name(track.file_path),
    }


def radio_track_ref(track: RadioTrack) -> dict[str, Any]:
    return {"uid": track.uid, "title": track.title, "artist": track.artist, "album": track.album, "file": file_name(track.file_path)}


def _target_ref(db: Session, target_type: ScheduleTargetType | None, target_id: int | None) -> dict[str, Any] | None:
    if target_type is None or target_id is None:
        return None
    if target_type == ScheduleTargetType.video:
        video = db.get(Video, target_id)
        return {"type": "video", "video": video_ref(video) if video else None}
    model = Playlist if target_type == ScheduleTargetType.playlist else RadioPlaylist
    playlist = db.get(model, target_id)
    return {"type": target_type.value, "uid": playlist.uid if playlist else None, "name": playlist.name if playlist else None}


def _duplicates(names) -> list[str]:
    return sorted(name for name, count in Counter(names).items() if count > 1)


_BOOLEAN_SETTINGS = {"auto_update_enabled", "auto_web_rendition", "media_native", "simplified_ui"}


def _settings_values(db: Session) -> dict[str, Any]:
    from app.api.routes.settings.values import get_settings

    return get_settings(db)


def _typed(key: str, value: Any) -> Any:
    return value == "true" if key in _BOOLEAN_SETTINGS and isinstance(value, str) else value


def _stored_int(db: Session, key: str, fallback: int) -> int:
    from app.models import Setting

    row = db.query(Setting).filter(Setting.key == key).first()
    if row is None or not row.value:
        return fallback
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return fallback


def build_settings(db: Session) -> dict[str, Any]:
    from app.config import settings as runtime_settings

    values = _settings_values(db)
    body = {key: _typed(key, values.get(key)) for key in PORTABLE_SETTINGS}
    background_id = values.get("default_coach_background_id")
    body["default_coach_background"] = background_ref(db.get(Background, background_id)) if background_id else None
    body["radio"] = {
        "volume_default": _stored_int(db, "radio_volume_default", runtime_settings.radio_volume_default),
        "crossfade_seconds": _stored_int(db, "radio_crossfade_seconds", runtime_settings.radio_crossfade_seconds),
        "announcement_duck_level": _stored_int(
            db, "radio_announcement_duck_level", runtime_settings.radio_announcement_duck_level,
        ),
    }
    return envelope("settings", {"settings": body})


def build_machine(db: Session) -> dict[str, Any]:
    from app.devices.audio_meta import load_audio_meta
    from app.devices.routing import load_routes
    from app.storage.library import global_defaults

    values = _settings_values(db)
    return envelope("machine", {"machine": {
        "display_mode": values.get("display_mode_setting"),
        "media_native": _typed("media_native", values.get("media_native")),
        "audio_routes": load_routes(db),
        "audio_outputs": load_audio_meta(db),
        "storage": global_defaults(db),
    }})


def build_display_outputs(db: Session) -> dict[str, Any]:
    from app.api.routes.settings.display import get_display_output_value
    from app.utils.video_sound import load_video_sound

    return envelope("display-outputs", {
        "outputs": {channel: get_display_output_value(db, channel) for channel in CHANNELS},
        "sound": {channel: load_video_sound(db, channel) for channel in CHANNELS},
    })


def build_radio_outputs(db: Session) -> dict[str, Any]:
    from app.api.contract import RADIO_CHANNELS
    from app.scheduling.radio import get_radio_default_playlist_override
    from app.radio.mix import load_mix
    from app.radio.sound import load_sound

    outputs = {}
    for channel in RADIO_CHANNELS:
        playlist_id = get_radio_default_playlist_override(db, channel)
        playlist = db.get(RadioPlaylist, playlist_id) if playlist_id else None
        outputs[channel] = {
            "sound": load_sound(db, channel), "mix": load_mix(db, channel),
            "default_playlist": playlist.name if playlist else None,
        }
    return envelope("radio-outputs", {"outputs": outputs})


def build_video_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(Playlist).order_by(Playlist.name).all()
    body = [{"uid": p.uid, "name": p.name, "videos": [video_ref(item.video) for item in p.items if item.video]} for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return envelope("playlists-video", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_audio_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(AudioPlaylist).order_by(AudioPlaylist.name).all()
    body = [{
        "uid": p.uid, "name": p.name,
        "tracks": [
            {"track": audio_track_ref(item.track), "background": background_ref(item.background)}
            for item in p.items if item.track
        ],
    } for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return envelope("playlists-audio", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_radio_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(RadioPlaylist).order_by(RadioPlaylist.name).all()
    body = [{
        "uid": p.uid, "name": p.name, "default": bool(p.is_default),
        "tracks": [radio_track_ref(item.track) for item in p.items if item.track],
    } for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return envelope("playlists-radio", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_radio_tags(db: Session) -> dict[str, Any]:
    tags = [{"uid": tag.uid, "name": tag.name} for tag in db.query(RadioTag).order_by(RadioTag.name).all()]
    tracks = db.query(RadioTrack).filter(RadioTrack.tags.any()).order_by(RadioTrack.title).all()
    assignments = [{"track": radio_track_ref(t), "tags": sorted(tag.name for tag in t.tags)} for t in tracks]
    return envelope("radio-tags", {"tags": tags, "assignments": assignments})


def build_announcements(db: Session) -> dict[str, Any]:
    announcements = db.query(RadioAnnouncement).order_by(RadioAnnouncement.description).all()
    body = [{"uid": a.uid, "description": a.description, "file": file_name(a.file_path), "enabled": bool(a.enabled)} for a in announcements]
    return envelope("announcements", {"announcements": body})


def build_announcement_rules(db: Session) -> dict[str, Any]:
    rules = db.query(RadioAnnouncementRule).order_by(RadioAnnouncementRule.created_at).all()
    body = []
    for rule in rules:
        entry: dict[str, Any] = {"uid": rule.uid, "type": rule.rule_type.value, "target": rule.target, "enabled": bool(rule.enabled)}
        if rule.n_tracks is not None:
            entry["n_tracks"] = rule.n_tracks
        if rule.interval_minutes is not None:
            entry["interval_minutes"] = rule.interval_minutes
        if rule.times_of_day:
            entry["times_of_day"] = json.loads(rule.times_of_day)
        body.append(entry)
    return envelope("announcement-rules", {"rules": body})


def _iso(value) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def build_schedule(db: Session, channel: str) -> dict[str, Any]:
    schedules = db.query(Schedule).filter(Schedule.channel == channel).order_by(Schedule.id).all()
    body = []
    for schedule in schedules:
        entry: dict[str, Any] = {
            "uid": schedule.uid,
            "target": _target_ref(db, schedule.target_type, schedule.target_id),
            "type": schedule.schedule_type.value,
            "active": bool(schedule.active),
        }
        if schedule.run_at is not None:
            entry["run_at"] = _iso(schedule.run_at)
        if schedule.recurrence_rule:
            entry["recurrence"] = json.loads(schedule.recurrence_rule)
        if schedule.overrides:
            entry["overrides"] = [{
                "uid": override.uid,
                "date": override.occurrence_date.date().isoformat(),
                "action": override.action.value,
                "replacement": _target_ref(db, override.replacement_target_type, override.replacement_target_id),
            } for override in sorted(schedule.overrides, key=lambda o: o.occurrence_date)]
        body.append(entry)
    return envelope(f"schedule-{channel.replace('_', '-')}", {"channel": channel, "schedules": body})


BUILDERS: dict[str, Callable[[Session], dict[str, Any]]] = {
    "settings.json": build_settings,
    "machine.json": build_machine,
    "outputs/display.json": build_display_outputs,
    "outputs/radio.json": build_radio_outputs,
    "library/videos.json": build_library_videos,
    "library/audio.json": build_library_audio,
    "library/radio.json": build_library_radio,
    "library/backgrounds.json": build_library_backgrounds,
    "library/announcements.json": build_announcements,
    "playlists/video.json": build_video_playlists,
    "playlists/audio.json": build_audio_playlists,
    "playlists/radio.json": build_radio_playlists,
    **{schedule_path(c): (lambda db, c=c: build_schedule(db, c)) for c in SCHEDULE_CHANNELS},
    "radio/tags.json": build_radio_tags,
    "radio/announcement-rules.json": build_announcement_rules,
}


def instance_uid(db: Session) -> str | None:
    from app.models import Setting

    row = db.query(Setting).filter(Setting.key == "instance_uid").first()
    return row.value if row else None


def build_manifest(db: Session, documents: dict[str, dict[str, Any]]) -> dict[str, Any]:
    from app.utils.version import get_app_version

    def count(document: dict[str, Any]) -> int | None:
        lists = [value for key, value in document.items() if isinstance(value, list) and key != "warnings"]
        return len(lists[0]) if lists else None

    return envelope("manifest", {
        "app_version": get_app_version(), "instance": instance_uid(db),
        "files": {name: count(document) for name, document in documents.items()},
    })


def export_all(db: Session) -> dict[str, dict[str, Any]]:
    documents = {name: builder(db) for name, builder in BUILDERS.items()}
    return {"manifest.json": build_manifest(db, documents), **documents}

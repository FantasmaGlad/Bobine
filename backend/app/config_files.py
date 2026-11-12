"""Configuration de Bobine en fichiers JSON lisibles, rangés par famille."""
from __future__ import annotations

import json
from app.api.contract import CHANNELS
import logging
import os
import tempfile
import threading
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.models import (
    AudioPlaylist, AudioTrack, Background, Playlist, RadioAnnouncement, RadioAnnouncementRule, RadioPlaylist,
    RadioTag, RadioTrack, Schedule, ScheduleTargetType, Video,
)

logger = logging.getLogger(__name__)

SCHEMA = 2
ACCEPTED_SCHEMAS = (1, 2)
SCHEDULE_CHANNELS = ("cable", "network", "radio_cable", "radio_network")


def schedule_path(channel: str) -> str:
    return f"schedule/{channel.replace('_', '-')}.json"


KINDS: dict[str, str] = {
    "manifest.json": "manifest",
    "settings.json": "settings",
    "machine.json": "machine",
    "outputs/display.json": "display-outputs",
    "outputs/radio.json": "radio-outputs",
    "library/videos.json": "library-videos",
    "library/audio.json": "library-audio",
    "library/radio.json": "library-radio",
    "library/backgrounds.json": "library-backgrounds",
    "library/announcements.json": "announcements",
    "playlists/video.json": "playlists-video",
    "playlists/audio.json": "playlists-audio",
    "playlists/radio.json": "playlists-radio",
    **{schedule_path(c): f"schedule-{c.replace('_', '-')}" for c in SCHEDULE_CHANNELS},
    "radio/tags.json": "radio-tags",
    "radio/announcement-rules.json": "announcement-rules",
}
LEGACY_NAMES: dict[str, str] = {
    "display-outputs.json": "outputs/display.json",
    "radio-outputs.json": "outputs/radio.json",
    "announcements.json": "library/announcements.json",
    "playlists-video.json": "playlists/video.json",
    "playlists-audio.json": "playlists/audio.json",
    "playlists-radio.json": "playlists/radio.json",
    **{f"schedule-{c.replace('_', '-')}.json": schedule_path(c) for c in SCHEDULE_CHANNELS},
    "radio-tags.json": "radio/tags.json",
    "announcement-rules.json": "radio/announcement-rules.json",
}


def canonical_name(name: str) -> str:
    """Nom d'un fichier dans l'arborescence actuelle (traduit les noms plats de la version 5.1)."""
    return LEGACY_NAMES.get(name.replace("\\", "/"), name.replace("\\", "/"))

PORTABLE_SETTINGS = (
    "theme", "theme_mode", "language", "active_logo", "update_channel", "auto_update_enabled", "auto_update_time",
    "wait_time_between_courses", "volume_default", "audio_chain_timer_seconds", "logs_retention_days",
    "radio_announcement_fade_ms", "auto_web_rendition", "simplified_ui",
)
_BOOLEAN_SETTINGS = {"auto_update_enabled", "auto_web_rendition", "media_native", "update_tor", "simplified_ui"}


def _file_name(path: str | None) -> str | None:
    return Path(path).name if path else None


def video_ref(video: Video) -> dict[str, Any]:
    return {"uid": video.uid, "title": video.title, "program": video.program, "release": video.release, "file": _file_name(video.file_path)}


def background_ref(background: Background | None) -> dict[str, Any] | None:
    if background is None:
        return None
    return {"uid": background.uid, "title": background.title, "file": _file_name(background.file_path)}


def audio_track_ref(track: AudioTrack) -> dict[str, Any]:
    course = track.course
    return {
        "uid": track.uid,
        "course": {"uid": course.uid, "title": course.title, "program": course.program, "release": course.release},
        "number": track.number, "title": track.title, "file": _file_name(track.file_path),
    }


def radio_track_ref(track: RadioTrack) -> dict[str, Any]:
    return {"uid": track.uid, "title": track.title, "artist": track.artist, "album": track.album, "file": _file_name(track.file_path)}


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


def _document(kind: str, body: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    document: dict[str, Any] = {"schema": SCHEMA, "kind": kind, **body}
    if warnings:
        document["warnings"] = warnings
    return document


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
    return _document("settings", {"settings": body})


def build_machine(db: Session) -> dict[str, Any]:
    from app.devices.routing import load_routes
    from app.api.routes.devices import _load_audio_meta
    from app.storage.library import global_defaults

    values = _settings_values(db)
    return _document("machine", {"machine": {
        "display_mode": values.get("display_mode_setting"),
        "media_native": _typed("media_native", values.get("media_native")),
        "update_tor": _typed("update_tor", values.get("update_tor")),
        "update_tor_proxy": values.get("update_tor_proxy"),
        "audio_routes": load_routes(db),
        "audio_outputs": _load_audio_meta(db),
        "storage": global_defaults(db),
    }})


def build_display_outputs(db: Session) -> dict[str, Any]:
    from app.api.routes.settings.display import get_display_output_value

    from app.utils.video_sound import load_video_sound

    return _document("display-outputs", {
        "outputs": {channel: get_display_output_value(db, channel) for channel in CHANNELS},
        "sound": {channel: load_video_sound(db, channel) for channel in CHANNELS},
    })


def build_radio_outputs(db: Session) -> dict[str, Any]:
    from app.radio_manager import RADIO_CHANNELS
    from app.scheduling.radio import get_radio_default_playlist_override
    from app.utils.radio_mix import load_mix
    from app.utils.radio_sound import load_sound

    outputs = {}
    for channel in RADIO_CHANNELS:
        playlist_id = get_radio_default_playlist_override(db, channel)
        playlist = db.get(RadioPlaylist, playlist_id) if playlist_id else None
        outputs[channel] = {
            "sound": load_sound(db, channel), "mix": load_mix(db, channel),
            "default_playlist": playlist.name if playlist else None,
        }
    return _document("radio-outputs", {"outputs": outputs})


def build_video_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(Playlist).order_by(Playlist.name).all()
    body = [{"uid": p.uid, "name": p.name, "videos": [video_ref(item.video) for item in p.items if item.video]} for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return _document("playlists-video", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


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
    return _document("playlists-audio", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_radio_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(RadioPlaylist).order_by(RadioPlaylist.name).all()
    body = [{
        "uid": p.uid, "name": p.name, "default": bool(p.is_default),
        "tracks": [radio_track_ref(item.track) for item in p.items if item.track],
    } for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return _document("playlists-radio", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_radio_tags(db: Session) -> dict[str, Any]:
    tags = [{"uid": tag.uid, "name": tag.name} for tag in db.query(RadioTag).order_by(RadioTag.name).all()]
    tracks = db.query(RadioTrack).filter(RadioTrack.tags.any()).order_by(RadioTrack.title).all()
    assignments = [{"track": radio_track_ref(t), "tags": sorted(tag.name for tag in t.tags)} for t in tracks]
    return _document("radio-tags", {"tags": tags, "assignments": assignments})


def build_announcements(db: Session) -> dict[str, Any]:
    announcements = db.query(RadioAnnouncement).order_by(RadioAnnouncement.description).all()
    body = [{"uid": a.uid, "description": a.description, "file": _file_name(a.file_path), "enabled": bool(a.enabled)} for a in announcements]
    return _document("announcements", {"announcements": body})


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
    return _document("announcement-rules", {"rules": body})


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
    return _document(f"schedule-{channel.replace('_', '-')}", {"channel": channel, "schedules": body})


def _ordered(db: Session, model, *keys):
    return db.query(model).order_by(*keys, model.id).all()


def build_library_videos(db: Session) -> dict[str, Any]:
    videos = _ordered(db, Video, Video.title)
    return _document("library-videos", {"videos": [_video_entry(v) for v in videos]})


def _linked_file(path: str | None) -> dict[str, str] | None:
    return {"file": Path(path).name, "path": path} if path else None


def _video_entry(v: Video) -> dict[str, Any]:
    subtitles = sorted(v.subtitles, key=lambda s: (s.language_code, s.id))
    return {
        "uid": v.uid, "title": v.title, "program": v.program, "release": v.release, "description": v.description,
        "file": _file_name(v.file_path),
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
    return _document("library-audio", {"courses": [{
        "uid": c.uid, "title": c.title, "program": c.program, "release": c.release,
        "tracks": [{"uid": t.uid, "number": t.number, "title": t.title, "file": _file_name(t.file_path)}
                   for t in sorted(c.tracks, key=lambda t: (t.number or 0, t.id))],
    } for c in courses]})


def build_library_radio(db: Session) -> dict[str, Any]:
    tracks = _ordered(db, RadioTrack, RadioTrack.title)
    return _document("library-radio", {"tracks": [{
        "uid": t.uid, "title": t.title, "artist": t.artist, "album": t.album, "album_artist": t.album_artist,
        "genre": t.genre, "track_number": t.track_number, "disc_number": t.disc_number, "year": t.year,
        "file": _file_name(t.file_path),
    } for t in tracks]})


def build_library_backgrounds(db: Session) -> dict[str, Any]:
    backgrounds = _ordered(db, Background, Background.title)
    return _document("library-backgrounds", {"backgrounds": [
        {"uid": b.uid, "title": b.title, "file": _file_name(b.file_path)} for b in backgrounds]})


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

    return _document("manifest", {
        "app_version": get_app_version(), "instance": instance_uid(db),
        "files": {name: count(document) for name, document in documents.items()},
    })


def export_all(db: Session) -> dict[str, dict[str, Any]]:
    documents = {name: builder(db) for name, builder in BUILDERS.items()}
    return {"manifest.json": build_manifest(db, documents), **documents}


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


MIRROR_DELAY_SECONDS = 2.0
_mirror_lock = threading.Lock()
_mirror_timer: threading.Timer | None = None


def mirror_dir() -> Path:
    """`config/` à côté des journaux, dans le dossier de données de Bobine (jamais dans le dossier du code, qui est un dépôt git sur l'appliance)."""
    from app.config import settings as runtime_settings

    return Path(runtime_settings.logs_dir).parent / "config"


def write_mirror() -> int:
    """Réécrit les fichiers dont le contenu a changé (écriture atomique) ; renvoie leur nombre."""
    from app.database import SessionLocal

    target = mirror_dir()
    target.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        documents = export_all(db)
    written = 0
    for name, document in documents.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = dumps(document)
        try:
            if path.read_text(encoding="utf-8") == content:
                continue
        except OSError:
            pass
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(content)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        written += 1
    for legacy in LEGACY_NAMES:
        (target / legacy).unlink(missing_ok=True)
    return written


def _mirror_now() -> None:
    global _mirror_timer
    with _mirror_lock:
        _mirror_timer = None
    try:
        write_mirror()
    except Exception as exc:
        logger.warning("Copie de la configuration dans %s impossible : %s", mirror_dir(), exc)


def schedule_mirror() -> None:
    """Demande une mise à jour de la copie ; plusieurs demandes rapprochées n'en font qu'une."""
    global _mirror_timer
    with _mirror_lock:
        if _mirror_timer is not None:
            _mirror_timer.cancel()
        _mirror_timer = threading.Timer(MIRROR_DELAY_SECONDS, _mirror_now)
        _mirror_timer.daemon = True
        _mirror_timer.start()


class ConfigMirrorTrigger:
    """Après chaque requête réussie qui modifie quelque chose sous `/api/`, demande la mise à jour de la copie : un seul point d'accroche pour toutes les routes, présentes et futures."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS") or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        status = 0

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, capture)
        if 200 <= status < 300:
            schedule_mirror()

"""Configuration de Bobine en fichiers JSON lisibles, un fichier par type de réglage.

Chaque fichier porte `schema` et `kind` et se suffit à lui-même : on peut le lire, le comparer, le modifier à la main
puis le réappliquer seul. Les objets se désignent par leur nom ou leurs métadonnées (titre, programme, nom de fichier),
jamais par un identifiant interne, qui change d'une installation à l'autre. Les médias (vidéos, cours, morceaux,
annonces) ne sont pas transportés : les fichiers y font référence. `machine.json` regroupe ce qui ne vaut que pour cette
machine (écrans, sorties audio, composant natif, Tor, supports).

Une copie à jour est écrite dans le dossier `config/` des données de Bobine après chaque modification : c'est un instantané pour lire et
déboguer, jamais relu automatiquement.
"""
from __future__ import annotations

import json
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

SCHEMA = 1
SCHEDULE_CHANNELS = ("cable", "network", "radio_cable", "radio_network")

# Réglages communs à toutes les installations, tels que l'interface les affiche (valeurs effectives).
PORTABLE_SETTINGS = (
    "theme", "language", "active_logo", "update_channel", "auto_update_enabled", "auto_update_time",
    "wait_time_between_courses", "volume_default", "audio_chain_timer_seconds", "logs_retention_days",
    "radio_announcement_fade_ms", "auto_web_rendition",
)
_BOOLEAN_SETTINGS = {"auto_update_enabled", "auto_web_rendition", "media_native", "update_tor"}


# --- références lisibles ---------------------------------------------------------------------------------------------

def _file_name(path: str | None) -> str | None:
    return Path(path).name if path else None


def video_ref(video: Video) -> dict[str, Any]:
    return {"title": video.title, "program": video.program, "release": video.release, "file": _file_name(video.file_path)}


def background_ref(background: Background | None) -> dict[str, Any] | None:
    if background is None:
        return None
    return {"title": background.title, "file": _file_name(background.file_path)}


def audio_track_ref(track: AudioTrack) -> dict[str, Any]:
    course = track.course
    return {
        "course": {"title": course.title, "program": course.program, "release": course.release},
        "number": track.number, "title": track.title, "file": _file_name(track.file_path),
    }


def radio_track_ref(track: RadioTrack) -> dict[str, Any]:
    return {"title": track.title, "artist": track.artist, "album": track.album, "file": _file_name(track.file_path)}


def _target_ref(db: Session, target_type: ScheduleTargetType | None, target_id: int | None) -> dict[str, Any] | None:
    if target_type is None or target_id is None:
        return None
    if target_type == ScheduleTargetType.video:
        video = db.get(Video, target_id)
        return {"type": "video", "video": video_ref(video) if video else None}
    model = Playlist if target_type == ScheduleTargetType.playlist else RadioPlaylist
    playlist = db.get(model, target_id)
    return {"type": target_type.value, "name": playlist.name if playlist else None}


def _duplicates(names) -> list[str]:
    return sorted(name for name, count in Counter(names).items() if count > 1)


def _document(kind: str, body: dict[str, Any], warnings: list[str] | None = None) -> dict[str, Any]:
    document: dict[str, Any] = {"schema": SCHEMA, "kind": kind, **body}
    if warnings:
        # Signalé dans le fichier même : `apply` refusera ces références ambiguës tant qu'elles ne sont pas levées.
        document["warnings"] = warnings
    return document


# --- un constructeur par fichier ---------------------------------------------------------------------------------------

def _settings_values(db: Session) -> dict[str, Any]:
    from app.routers.settings import get_settings

    return get_settings(db)


def _typed(key: str, value: Any) -> Any:
    return value == "true" if key in _BOOLEAN_SETTINGS and isinstance(value, str) else value


def _stored_int(db: Session, key: str, fallback: int) -> int:
    """Valeur entière persistée dans la table `settings`, ou `fallback` (config.toml) si la ligne est absente ou illisible."""
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
    # Lus au démarrage seulement : leur valeur effective dans le processus n'est actualisée qu'au prochain lancement.
    # Le fichier décrit la valeur PERSISTÉE, pas celle du singleton : après une application, l'export doit renvoyer le
    # réglage appliqué (sinon l'aller-retour export → application → export perd la modification).
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
    from app.routers.devices import _load_audio_meta
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
    from app.routers.settings import get_display_output_value

    return _document("display-outputs", {"outputs": {
        channel: get_display_output_value(db, channel) for channel in ("cable", "network")
    }})


def build_radio_outputs(db: Session) -> dict[str, Any]:
    from app.radio_manager import RADIO_CHANNELS
    from app.scheduler_manager import get_radio_default_playlist_override
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
    body = [{"name": p.name, "videos": [video_ref(item.video) for item in p.items if item.video]} for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return _document("playlists-video", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_audio_playlists(db: Session) -> dict[str, Any]:
    playlists = db.query(AudioPlaylist).order_by(AudioPlaylist.name).all()
    body = [{
        "name": p.name,
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
        "name": p.name, "default": bool(p.is_default),
        "tracks": [radio_track_ref(item.track) for item in p.items if item.track],
    } for p in playlists]
    duplicates = _duplicates(p.name for p in playlists)
    return _document("playlists-radio", {"playlists": body}, [f"playlist en double : {n}" for n in duplicates])


def build_radio_tags(db: Session) -> dict[str, Any]:
    tags = [tag.name for tag in db.query(RadioTag).order_by(RadioTag.name).all()]
    tracks = db.query(RadioTrack).filter(RadioTrack.tags.any()).order_by(RadioTrack.title).all()
    assignments = [{"track": radio_track_ref(t), "tags": sorted(tag.name for tag in t.tags)} for t in tracks]
    return _document("radio-tags", {"tags": tags, "assignments": assignments})


def build_announcements(db: Session) -> dict[str, Any]:
    announcements = db.query(RadioAnnouncement).order_by(RadioAnnouncement.description).all()
    body = [{"description": a.description, "file": _file_name(a.file_path), "enabled": bool(a.enabled)} for a in announcements]
    return _document("announcements", {"announcements": body})


def build_announcement_rules(db: Session) -> dict[str, Any]:
    rules = db.query(RadioAnnouncementRule).order_by(RadioAnnouncementRule.created_at).all()
    body = []
    for rule in rules:
        entry: dict[str, Any] = {"type": rule.rule_type.value, "target": rule.target, "enabled": bool(rule.enabled)}
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
                "date": override.occurrence_date.date().isoformat(),
                "action": override.action.value,
                "replacement": _target_ref(db, override.replacement_target_type, override.replacement_target_id),
            } for override in sorted(schedule.overrides, key=lambda o: o.occurrence_date)]
        body.append(entry)
    return _document(f"schedule-{channel.replace('_', '-')}", {"channel": channel, "schedules": body})


BUILDERS: dict[str, Callable[[Session], dict[str, Any]]] = {
    "settings.json": build_settings,
    "display-outputs.json": build_display_outputs,
    "radio-outputs.json": build_radio_outputs,
    "playlists-video.json": build_video_playlists,
    "playlists-audio.json": build_audio_playlists,
    "playlists-radio.json": build_radio_playlists,
    "radio-tags.json": build_radio_tags,
    "announcements.json": build_announcements,
    "announcement-rules.json": build_announcement_rules,
    **{f"schedule-{c.replace('_', '-')}.json": (lambda db, c=c: build_schedule(db, c)) for c in SCHEDULE_CHANNELS},
    "machine.json": build_machine,
}


def export_all(db: Session) -> dict[str, dict[str, Any]]:
    return {name: builder(db) for name, builder in BUILDERS.items()}


def dumps(document: dict[str, Any]) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


# --- copie lisible dans les données de Bobine --------------------------------------------------------------------------

MIRROR_DELAY_SECONDS = 2.0
_mirror_lock = threading.Lock()
_mirror_timer: threading.Timer | None = None


def mirror_dir() -> Path:
    """`config/` à côté des journaux, dans le dossier de données de Bobine (jamais dans le dossier du code, qui est un
    dépôt git sur l'appliance)."""
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
        content = dumps(document)
        try:
            if path.read_text(encoding="utf-8") == content:
                continue
        except OSError:
            pass
        handle, temporary = tempfile.mkstemp(dir=target, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(content)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        written += 1
    return written


def _mirror_now() -> None:
    global _mirror_timer
    with _mirror_lock:
        _mirror_timer = None
    try:
        write_mirror()
    except Exception as exc:  # une copie de lecture ne doit jamais gêner Bobine
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
    """Après chaque requête réussie qui modifie quelque chose sous `/api/`, demande la mise à jour de la copie : un seul
    point d'accroche pour toutes les routes, présentes et futures."""

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

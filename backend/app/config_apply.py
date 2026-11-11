"""Application des fichiers de configuration (`app/config_files.py`) : tout ou rien.

Chaque fichier décrit l'état voulu de son type de réglage. Toutes les références (vidéos, pistes, morceaux, fonds,
playlists) sont d'abord résolues et toutes les valeurs validées, avec les mêmes règles que l'interface ; la moindre
erreur refuse l'ensemble et les liste toutes. Sinon tout est écrit dans une seule transaction, puis les effets à chaud
(diffusion aux écrans, planificateur, moteurs radio) suivent. L'essai à blanc renvoie l'écart sans rien écrire.

Reconnaissance des objets : par `uid` (identifiant stable) quand il est présent et connu ; sinon par le nom ou les
métadonnées, comme dans les fichiers de la version 5.1. Un `uid` inconnu ici crée l'objet avec ce `uid` (restauration
sur une autre installation) ; un objet reconnu par son `uid` dont le nom a changé est renommé.

Sémantique par fichier : réglages et sorties = valeurs fournies ; playlists et étiquettes = créées, renommées ou
remplacées, les autres restent sauf `"prune": true` (elles sont alors supprimées) ; `library/` = métadonnées des médias
existants (jamais de création ni de suppression de média) ; annonces = description et activation des annonces existantes ;
règles d'annonce et planning d'un canal = liste complète (ce qui n'y figure plus est supprimé, les `id` des programmations
reconnues sont conservés).
"""
from __future__ import annotations

import difflib
import json
from app.api.contract import CHANNELS
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.utils import ui_language
from app import config_files
from app.utils.uid import is_uid
from app.models import (
    AudioCourse, AudioPlaylist, AudioPlaylistItem, AudioTrack, Background, OverrideAction, Playlist, PlaylistItem,
    RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType, RadioPlaylist, RadioPlaylistItem, RadioTag,
    RadioTrack, Schedule, ScheduleOverride, ScheduleTargetType, ScheduleType, Setting, Video,
)

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_START_ONLY_RADIO = {"volume_default": "radio_volume_default", "crossfade_seconds": "radio_crossfade_seconds",
                     "announcement_duck_level": "radio_announcement_duck_level"}


class ConfigErrors(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class _Context:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.errors: list[str] = []
        self.effects: list[Callable[[Session], Awaitable[None]]] = []
        self.restart_required: list[str] = []

    def fail(self, file: str, message: str) -> None:
        self.errors.append(f"{file} : {message}")


# --- résolution des références ---------------------------------------------------------------------------------------

def _pick(ctx: _Context, file: str, what: str, candidates: list, ref: dict, path_of: Callable[[Any], str | None]):
    wanted = (ref or {}).get("file")
    if wanted:
        candidates = [c for c in candidates if path_of(c) and Path(path_of(c)).name == wanted]
    if len(candidates) == 1:
        return candidates[0]
    ctx.fail(file, f"{what} {'introuvable' if not candidates else 'ambigu (préciser « file »)'} : {json.dumps(ref, ensure_ascii=False)}")
    return None


def _by_uid(ctx: _Context, model, ref: Any):
    """Objet portant le `uid` de `ref` (None sans `uid` valide ou s'il est inconnu ici)."""
    uid = ref.get("uid") if isinstance(ref, dict) else None
    return ctx.db.query(model).filter(model.uid == uid).first() if is_uid(uid) else None


def _claim_uid(ctx: _Context, model, entry: Any, obj: Any) -> None:
    """Un objet créé reprend le `uid` du document s'il est valide et libre (restauration sur une autre installation)."""
    uid = entry.get("uid") if isinstance(entry, dict) else None
    # Le préfixe fait partie de l'identité (`pl_`, `tag_`...) : un `vid_` glissé dans un fichier de
    # playlists ne doit pas devenir l'uid d'une playlist.
    if is_uid(uid, getattr(model, "__uid_prefix__", None)) and not ctx.db.query(model).filter(model.uid == uid).first():
        obj.uid = uid


def _video(ctx: _Context, file: str, ref: dict) -> Video | None:
    found = _by_uid(ctx, Video, ref)
    if found is not None:
        return found
    if not isinstance(ref, dict) or not ref.get("title"):
        ctx.fail(file, f"vidéo invalide : {ref!r}")
        return None
    query = ctx.db.query(Video).filter(Video.title == ref["title"])
    for field in ("program", "release"):
        if field in ref:
            query = query.filter(getattr(Video, field) == ref[field])
    return _pick(ctx, file, "vidéo", query.all(), ref, lambda v: v.file_path)


def _background(ctx: _Context, file: str, ref: dict | None) -> Background | None:
    if ref is None:
        return None
    found = _by_uid(ctx, Background, ref)
    if found is not None:
        return found
    candidates = ctx.db.query(Background).filter(Background.title == (ref or {}).get("title")).all()
    return _pick(ctx, file, "fond", candidates, ref, lambda b: b.file_path)


def _audio_track(ctx: _Context, file: str, ref: dict) -> AudioTrack | None:
    found = _by_uid(ctx, AudioTrack, ref)
    if found is not None:
        return found
    course_ref = (ref or {}).get("course") or {}
    query = ctx.db.query(AudioTrack).join(AudioCourse).filter(AudioTrack.title == (ref or {}).get("title"),
                                                               AudioCourse.title == course_ref.get("title"))
    for field in ("program", "release"):
        if field in course_ref:
            query = query.filter(getattr(AudioCourse, field) == course_ref[field])
    if ref.get("number") is not None:
        query = query.filter(AudioTrack.number == ref["number"])
    return _pick(ctx, file, "piste", query.all(), ref, lambda t: t.file_path)


def _radio_track(ctx: _Context, file: str, ref: dict) -> RadioTrack | None:
    found = _by_uid(ctx, RadioTrack, ref)
    if found is not None:
        return found
    query = ctx.db.query(RadioTrack).filter(RadioTrack.title == (ref or {}).get("title"))
    for field in ("artist", "album"):
        if field in ref:
            query = query.filter(getattr(RadioTrack, field) == ref[field])
    return _pick(ctx, file, "morceau", query.all(), ref, lambda t: t.file_path)


def _unique_by_name(ctx: _Context, file: str, model, name: str):
    """Playlist existante portant ce nom (None si aucune) ; un homonyme en base rend la cible ambiguë."""
    found = ctx.db.query(model).filter(model.name == name).all()
    if len(found) > 1:
        ctx.fail(file, f"plusieurs playlists « {name} » existent : renommez-en une avant d'appliquer")
    return found[0] if len(found) == 1 else None


def _names(ctx: _Context, file: str, entries: list) -> bool:
    names = [e.get("name") for e in entries if isinstance(e, dict)]
    if any(not isinstance(n, str) or not n.strip() for n in names) or len(names) != len(entries):
        ctx.fail(file, "chaque playlist doit avoir un nom")
        return False
    for name in config_files._duplicates(names):
        ctx.fail(file, f"playlist « {name} » présente deux fois")
    for uid in config_files._duplicates(e.get("uid") for e in entries if is_uid(e.get("uid"))):
        ctx.fail(file, f"uid {uid} présent deux fois")
    return True


def _list(ctx: _Context, file: str, document: dict, key: str) -> list:
    value = document.get(key)
    if not isinstance(value, list):
        ctx.fail(file, f"« {key} » doit être une liste")
        return []
    return value


def _flag(ctx: _Context, file: str, label: str, value: Any) -> bool:
    """Booléen JSON strict : la chaîne « false » ne doit pas valoir vrai par simple vérité Python."""
    if not isinstance(value, bool):
        ctx.fail(file, f"{label} doit être un booléen (true ou false)")
        return False
    return value


# --- un applicateur par fichier --------------------------------------------------------------------------------------

def _apply_settings(ctx: _Context, file: str, document: dict) -> None:
    from app.api.routes.settings import SettingsUpdate, after_settings_change, settings_updates, stage_settings

    body = document.get("settings")
    if not isinstance(body, dict):
        ctx.fail(file, "« settings » doit être un objet")
        return
    unknown = sorted(set(body) - set(config_files.PORTABLE_SETTINGS) - {"default_coach_background", "radio"})
    for key in unknown:
        ctx.fail(file, f"réglage inconnu : {key}")
    values: dict[str, Any] = {}
    for key in config_files.PORTABLE_SETTINGS:
        if key in body:
            value = body[key]
            values[key] = ("true" if value else "false") if isinstance(value, bool) else value
    if "default_coach_background" in body:
        background = _background(ctx, file, body["default_coach_background"])
        values["default_coach_background_id"] = background.id if background else 0
    _stage(ctx, file, values, SettingsUpdate, settings_updates, stage_settings, after_settings_change)
    if values.get("language") in ("fr", "en") and values["language"] != ui_language.served():
        ctx.restart_required.append("language")
    radio_value = body.get("radio")
    if radio_value is None:
        radio = {}
    elif not isinstance(radio_value, dict):
        ctx.fail(file, "« radio » doit être un objet")
        radio = {}
    else:
        radio = radio_value
    for key in sorted(set(radio) - set(_START_ONLY_RADIO)):
        ctx.fail(file, f"réglage radio inconnu : {key}")
    for key, setting_key in _START_ONLY_RADIO.items():
        if key in radio:
            value = radio[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                ctx.fail(file, f"radio.{key} doit être un entier positif")
                continue
            from app.config import settings as runtime_settings

            if value != config_files._stored_int(ctx.db, setting_key, getattr(runtime_settings, setting_key)):
                _write_setting(ctx.db, setting_key, str(value))
                ctx.restart_required.append(f"radio.{key}")


def _stage(ctx, file, values, model, to_updates, stage, after) -> None:
    if not values:
        return
    try:
        updates = to_updates(model(**values))
        stage(updates, ctx.db)
    except HTTPException as exc:
        ctx.fail(file, str(exc.detail))
        return
    except ValueError as exc:  # validation du modèle
        ctx.fail(file, str(exc))
        return

    async def effect(db: Session) -> None:
        await after(updates, db)

    ctx.effects.append(effect)


def _write_setting(db: Session, key: str, value: str | None) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def _apply_machine(ctx: _Context, file: str, document: dict) -> None:
    from app.devices.routing import ROUTES_SETTING, sanitize_routes
    from app.api.routes.settings import SettingsUpdate, after_settings_change, settings_updates, stage_settings
    from app.storage import longevity

    body = document.get("machine")
    if not isinstance(body, dict):
        ctx.fail(file, "« machine » doit être un objet")
        return
    unknown = sorted(set(body) - {
        "display_mode", "media_native", "update_tor", "update_tor_proxy", "audio_routes", "audio_outputs", "storage",
    })
    for key in unknown:
        ctx.fail(file, f"réglage machine inconnu : {key}")
    values: dict[str, Any] = {}
    for source, target in (("display_mode", "display_mode_setting"), ("media_native", "media_native"),
                           ("update_tor", "update_tor"), ("update_tor_proxy", "update_tor_proxy")):
        if source in body:
            value = body[source]
            values[target] = ("true" if value else "false") if isinstance(value, bool) else value
    _stage(ctx, file, values, SettingsUpdate, settings_updates, stage_settings, after_settings_change)
    if "audio_routes" in body:
        routes = sanitize_routes(body["audio_routes"])
        _write_setting(ctx.db, ROUTES_SETTING, json.dumps(routes, ensure_ascii=False) if routes else None)

        async def reconcile(db: Session) -> None:
            from app.devices.service import service as devices_service

            await devices_service.reconcile_routes()

        ctx.effects.append(reconcile)
    if "audio_outputs" in body:
        meta = body["audio_outputs"]
        if not isinstance(meta, dict) or len(meta) > 200 or any(
            len(str(key)) > 256 or not isinstance(value, dict) or len(str(value.get("alias") or "")) > 60
            for key, value in meta.items()
        ):
            ctx.fail(file, "« audio_outputs » invalide (200 sorties au plus, alias de 60 caractères au plus)")
        else:
            _write_setting(ctx.db, "devices_audio_meta", json.dumps(meta, ensure_ascii=False))
    if "storage" in body:
        try:
            _write_setting(ctx.db, "storage_defaults", json.dumps(longevity.normalize_settings(body["storage"])))
        except (TypeError, ValueError) as exc:
            ctx.fail(file, f"« storage » invalide : {exc}")


def _apply_display_outputs(ctx: _Context, file: str, document: dict) -> None:
    from app.api.routes.settings import _DISPLAY_OUTPUTS_BY_CHANNEL, apply_display_output, get_display_output_value

    outputs = document.get("outputs")
    if not isinstance(outputs, dict):
        ctx.fail(file, "« outputs » doit être un objet")
        return
    for channel, output in outputs.items():
        if output not in _DISPLAY_OUTPUTS_BY_CHANNEL.get(channel, ()):
            ctx.fail(file, f"sortie invalide pour {channel} : {output!r}")
        elif output != get_display_output_value(ctx.db, channel):

            async def switch(db: Session, channel=channel, output=output) -> None:
                await apply_display_output(db, channel, output)

            ctx.effects.append(switch)
    sounds = document.get("sound", {})
    if not isinstance(sounds, dict):
        ctx.fail(file, "« sound » doit être un objet")
        return
    from app.playback_manager import get_playback_manager
    from app.utils.radio_sound import sanitize_sound
    from app.utils.video_sound import video_sound_setting_key

    for channel, raw in sounds.items():
        if channel not in CHANNELS:
            ctx.fail(file, f"canal inconnu pour le son : {channel!r}")
            continue
        if not isinstance(raw, dict):
            ctx.fail(file, f"réglages de son invalides pour le canal {channel!r} (objet attendu)")
            continue
        sound = sanitize_sound(raw)
        _write_setting(ctx.db, video_sound_setting_key(channel), json.dumps(sound))

        async def set_video_sound(db: Session, channel=channel, sound=sound) -> None:
            await get_playback_manager(channel).set_sound(sound)

        ctx.effects.append(set_video_sound)


def _apply_radio_outputs(ctx: _Context, file: str, document: dict) -> None:
    from app.radio_manager import RADIO_CHANNELS, get_radio_manager
    from app.scheduling.radio import radio_default_playlist_key
    from app.utils.radio_mix import mix_setting_key, sanitize_mix
    from app.utils.radio_sound import sanitize_sound, sound_setting_key

    outputs = document.get("outputs")
    if not isinstance(outputs, dict):
        ctx.fail(file, "« outputs » doit être un objet")
        return
    for channel, entry in outputs.items():
        if channel not in RADIO_CHANNELS or not isinstance(entry, dict):
            ctx.fail(file, f"sortie radio inconnue : {channel!r}")
            continue
        if "sound" in entry:
            if not isinstance(entry["sound"], dict):
                ctx.fail(file, f"réglages de son invalides pour la sortie {channel!r} (objet attendu)")
            else:
                sound = sanitize_sound(entry["sound"])
                _write_setting(ctx.db, sound_setting_key(channel), json.dumps(sound))

                async def set_sound(db: Session, channel=channel, sound=sound) -> None:
                    await get_radio_manager(channel).set_sound(sound)

                ctx.effects.append(set_sound)
        if "mix" in entry:
            if not isinstance(entry["mix"], dict):
                ctx.fail(file, f"réglages de mixage invalides pour la sortie {channel!r} (objet attendu)")
            else:
                mix = sanitize_mix(entry["mix"])
                _write_setting(ctx.db, mix_setting_key(channel), json.dumps(mix))

                async def set_mix(db: Session, channel=channel, mix=mix) -> None:
                    await get_radio_manager(channel).set_mix(mix)

                ctx.effects.append(set_mix)
        if "default_playlist" in entry:
            name = entry["default_playlist"]
            playlist = _unique_by_name(ctx, file, RadioPlaylist, name) if name else None
            if name and playlist is None:
                ctx.fail(file, f"playlist radio introuvable : {name}")
            _write_setting(ctx.db, radio_default_playlist_key(channel), str(playlist.id) if playlist else None)


def _replace_playlist(ctx, file, model, entry, build_items, kept: list):
    """Crée, renomme ou remplace une playlist reconnue par son `uid`, à défaut par son nom."""
    name = entry["name"]
    playlist = _by_uid(ctx, model, entry) or _unique_by_name(ctx, file, model, name)
    items = build_items()
    if playlist is None:
        playlist = model(name=name)
        _claim_uid(ctx, model, entry, playlist)
        ctx.db.add(playlist)
    elif playlist.name != name:
        if ctx.db.query(model).filter(model.name == name, model.id != playlist.id).first():
            ctx.fail(file, f"renommage impossible : une playlist « {name} » existe déjà")
        else:
            playlist.name = name
    playlist.items = items
    kept.append(playlist)
    return playlist


def _prune(ctx: _Context, file: str, document: dict, model, kept: list) -> None:
    """`"prune": true` : supprime les objets du type absents du document (opt-in ; jamais pour les médias)."""
    if "prune" in document and not isinstance(document["prune"], bool):
        ctx.fail(file, "« prune » doit être un booléen (true ou false)")
        return
    if document.get("prune") is not True:
        return
    kept_ids = {obj.id for obj in kept if obj.id is not None}
    removed_ids = []
    for obj in ctx.db.query(model).all():
        if obj.id not in kept_ids:
            removed_ids.append(obj.id)
            ctx.db.delete(obj)
    target = {Playlist: ScheduleTargetType.playlist, RadioPlaylist: ScheduleTargetType.radio_playlist}.get(model)
    if target is not None and removed_ids:
        # Une programmation ne vise pas une playlist qui n'existe plus.
        for schedule in ctx.db.query(Schedule).filter(Schedule.target_type == target, Schedule.target_id.in_(removed_ids)).all():
            ctx.db.delete(schedule)
        ctx.effects.append(_resync_all_schedules(None))


def _resync_all_schedules(channel: str | None):
    async def resync(db: Session) -> None:
        from app.scheduling.jobs import sync_schedule_job

        for schedule in db.query(Schedule).all():
            if channel is None or schedule.channel == channel:
                sync_schedule_job(schedule)

    return resync


def _apply_video_playlists(ctx: _Context, file: str, document: dict) -> None:
    entries = _list(ctx, file, document, "playlists")
    if not _names(ctx, file, entries):
        return
    kept: list = []
    for entry in entries:
        videos_refs = entry.get("videos")
        if not isinstance(videos_refs, list):
            ctx.fail(file, f"playlist « {entry['name']} » : « videos » doit être une liste")
            continue
        videos = [_video(ctx, file, ref) for ref in videos_refs]
        _replace_playlist(ctx, file, Playlist, entry, lambda videos=videos: [
            PlaylistItem(video_id=v.id, position=i) for i, v in enumerate(videos) if v is not None
        ], kept)
    _prune(ctx, file, document, Playlist, kept)


def _apply_audio_playlists(ctx: _Context, file: str, document: dict) -> None:
    entries = _list(ctx, file, document, "playlists")
    if not _names(ctx, file, entries):
        return
    kept: list = []
    for entry in entries:
        tracks = entry.get("tracks")
        if not isinstance(tracks, list):
            ctx.fail(file, f"playlist « {entry['name']} » : « tracks » doit être une liste")
            continue
        resolved = [(_audio_track(ctx, file, item.get("track") or {}), _background(ctx, file, item.get("background")))
                    for item in tracks]
        _replace_playlist(ctx, file, AudioPlaylist, entry, lambda resolved=resolved: [
            AudioPlaylistItem(audio_track_id=t.id, position=i, background_id=b.id if b else None)
            for i, (t, b) in enumerate(resolved) if t is not None
        ], kept)
    _prune(ctx, file, document, AudioPlaylist, kept)


def _apply_radio_playlists(ctx: _Context, file: str, document: dict) -> None:
    entries = _list(ctx, file, document, "playlists")
    if not _names(ctx, file, entries):
        return
    defaults = [e["name"] for e in entries if e.get("default") is True]
    if len(defaults) > 1:
        ctx.fail(file, f"une seule playlist d'ambiance par défaut ({', '.join(defaults)})")
    kept: list = []
    default_playlist = None
    for entry in entries:
        tracks_refs = entry.get("tracks")
        if not isinstance(tracks_refs, list):
            ctx.fail(file, f"playlist « {entry['name']} » : « tracks » doit être une liste")
            continue
        tracks = [_radio_track(ctx, file, ref) for ref in tracks_refs]
        playlist = _replace_playlist(ctx, file, RadioPlaylist, entry, lambda tracks=tracks: [
            RadioPlaylistItem(radio_track_id=t.id, position=i) for i, t in enumerate(tracks) if t is not None
        ], kept)
        if "default" in entry:
            playlist.is_default = _flag(
                ctx, file, f"« default » de la playlist « {entry['name']} »", entry["default"],
            )
            if entry["default"] is True:
                default_playlist = playlist
    if default_playlist is not None:
        for other in ctx.db.query(RadioPlaylist).filter(RadioPlaylist.id != default_playlist.id).all():
            other.is_default = False
    _prune(ctx, file, document, RadioPlaylist, kept)


def _apply_radio_tags(ctx: _Context, file: str, document: dict) -> None:
    by_name = {tag.name: tag for tag in ctx.db.query(RadioTag).all()}
    kept: list = []

    def tag(entry) -> RadioTag | None:
        """`entry` : un nom (version 5.1) ou `{"uid", "name"}`."""
        name = entry.get("name") if isinstance(entry, dict) else entry
        if not isinstance(name, str) or not name.strip():
            ctx.fail(file, f"étiquette invalide : {entry!r}")
            return None
        found = _by_uid(ctx, RadioTag, entry) if isinstance(entry, dict) else None
        if found is not None and found.name != name:
            if name in by_name and by_name[name] is not found:
                ctx.fail(file, f"renommage impossible : l'étiquette « {name} » existe déjà")
            else:
                by_name.pop(found.name, None)
                found.name = name
                by_name[name] = found
        found = found or by_name.get(name)
        if found is None:
            found = RadioTag(name=name)
            _claim_uid(ctx, RadioTag, entry, found)
            ctx.db.add(found)
            by_name[name] = found
        if found not in kept:
            kept.append(found)
        return found

    for entry in document.get("tags") or []:
        tag(entry)
    for assignment in document.get("assignments") or []:
        track = _radio_track(ctx, file, (assignment or {}).get("track") or {})
        tags = [tag(name) for name in (assignment or {}).get("tags") or []]
        if track is not None:
            track.tags = [t for t in tags if t is not None]
    _prune(ctx, file, document, RadioTag, kept)


def _apply_announcements(ctx: _Context, file: str, document: dict) -> None:
    for entry in _list(ctx, file, document, "announcements"):
        entry = entry or {}
        announcement = _by_uid(ctx, RadioAnnouncement, entry)
        if announcement is None:
            candidates = ctx.db.query(RadioAnnouncement).filter(RadioAnnouncement.description == entry.get("description")).all()
            announcement = _pick(ctx, file, "annonce", candidates, entry, lambda a: a.file_path)
        if announcement is None:
            continue
        description = entry.get("description")
        if description is not None and description != announcement.description:
            if not isinstance(description, str) or not description.strip():
                ctx.fail(file, f"description d'annonce invalide : {description!r}")
            else:
                announcement.description = description.strip()
        if "enabled" in entry:
            announcement.enabled = _flag(
                ctx, file, f"« enabled » de l'annonce « {entry.get('description')} »", entry["enabled"],
            )


def _apply_announcement_rules(ctx: _Context, file: str, document: dict) -> None:
    from app.radio_manager import RULE_TARGETS

    rules = []
    for entry in _list(ctx, file, document, "rules"):
        try:
            rule_type = RadioAnnouncementRuleType(entry.get("type"))
        except (ValueError, AttributeError):
            ctx.fail(file, f"type de règle invalide : {entry!r}")
            continue
        target = entry.get("target", "radio_network")
        times = entry.get("times_of_day")
        if target not in RULE_TARGETS:
            ctx.fail(file, f"sortie de règle invalide : {target!r}")
        if rule_type == RadioAnnouncementRuleType.every_n_tracks and not (isinstance(entry.get("n_tracks"), int) and entry["n_tracks"] >= 1):
            ctx.fail(file, "n_tracks (entier, au moins 1) requis pour every_n_tracks")
        if rule_type == RadioAnnouncementRuleType.every_x_minutes and not (isinstance(entry.get("interval_minutes"), int) and entry["interval_minutes"] >= 1):
            ctx.fail(file, "interval_minutes (entier, au moins 1) requis pour every_x_minutes")
        if rule_type == RadioAnnouncementRuleType.fixed_times and (not times or not all(isinstance(t, str) and _TIME_RE.match(t) for t in times)):
            ctx.fail(file, "times_of_day (liste d'horaires HH:MM) requis pour fixed_times")
        rule = RadioAnnouncementRule(
            rule_type=rule_type, target=target,
            enabled=_flag(ctx, file, "« enabled » de la règle", entry.get("enabled", True)),
            n_tracks=entry.get("n_tracks"), interval_minutes=entry.get("interval_minutes"),
            times_of_day=json.dumps(times) if times else None,
        )
        if is_uid(entry.get("uid"), "rul") and all(entry["uid"] != other.uid for other in rules):
            rule.uid = entry["uid"]
        rules.append(rule)
    ctx.db.query(RadioAnnouncementRule).delete()
    ctx.db.add_all(rules)


def _schedule_target(ctx: _Context, file: str, ref: dict | None) -> tuple[ScheduleTargetType, int] | None:
    kind = (ref or {}).get("type")
    if kind == "video":
        video = _video(ctx, file, (ref or {}).get("video") or {})
        return (ScheduleTargetType.video, video.id) if video else None
    if kind in ("playlist", "radio_playlist"):
        model = Playlist if kind == "playlist" else RadioPlaylist
        playlist = _by_uid(ctx, model, ref) or _unique_by_name(ctx, file, model, (ref or {}).get("name"))
        if playlist is None:
            ctx.fail(file, f"playlist introuvable : {(ref or {}).get('name')!r}")
            return None
        return ScheduleTargetType(kind), playlist.id
    ctx.fail(file, f"cible invalide : {ref!r}")
    return None


def _signature(schedule: Schedule) -> tuple:
    rule = json.dumps(json.loads(schedule.recurrence_rule), sort_keys=True) if schedule.recurrence_rule else None
    return (schedule.target_type, schedule.target_id, schedule.schedule_type, config_files._iso(schedule.run_at), rule)


def _apply_schedule(ctx: _Context, file: str, document: dict, channel: str) -> None:
    from app.scheduling.occurrences import ensure_utc

    if document.get("channel", channel) != channel:
        ctx.fail(file, f"« channel » doit valoir {channel}")
        return
    radio = channel.startswith("radio_")
    existing = ctx.db.query(Schedule).filter(Schedule.channel == channel).all()
    by_uid = {s.uid: s for s in existing}
    unused = list(existing)
    kept: list[Schedule] = []
    entries = _list(ctx, file, document, "schedules")
    for uid in config_files._duplicates(e.get("uid") for e in entries if isinstance(e, dict) and is_uid(e.get("uid"))):
        ctx.fail(file, f"uid {uid} présent deux fois")
    for entry in entries:
        entry = entry or {}
        target = _schedule_target(ctx, file, entry.get("target"))
        if target is None:
            continue
        if (target[0] == ScheduleTargetType.radio_playlist) != radio:
            ctx.fail(file, f"cible {target[0].value} impossible sur le canal {channel}")
            continue
        wanted = Schedule(
            target_type=target[0], target_id=target[1], channel=channel,
            active=_flag(ctx, file, "« active » de la programmation", entry.get("active", True)),
        )
        if entry.get("type") == "once":
            try:
                wanted.schedule_type, wanted.run_at = ScheduleType.once, ensure_utc(datetime.fromisoformat(entry["run_at"]))
            except (KeyError, TypeError, ValueError):
                ctx.fail(file, f"run_at (date ISO 8601) requis pour une programmation ponctuelle : {entry!r}")
                continue
        elif entry.get("type") == "recurring":
            rule = entry.get("recurrence") or {}
            days, time = rule.get("days_of_week"), rule.get("time")
            if not days or any(not isinstance(d, int) or not 0 <= d <= 6 for d in days) or not isinstance(time, str) or not _TIME_RE.match(time):
                ctx.fail(file, f"recurrence invalide (days_of_week 0 à 6, time HH:MM) : {rule!r}")
                continue
            end = rule.get("end_time")
            if end is not None and (not radio or not _TIME_RE.match(str(end)) or end <= time):
                ctx.fail(file, f"end_time invalide (radio seulement, après time) : {rule!r}")
                continue
            wanted.schedule_type, wanted.recurrence_rule = ScheduleType.recurring, json.dumps(
                {**{k: v for k, v in rule.items() if k in ("end_time", "mode")}, "days_of_week": sorted(set(days)), "time": time})
        else:
            ctx.fail(file, f"type de programmation invalide : {entry.get('type')!r}")
            continue
        overrides = []
        for override in entry.get("overrides") or []:
            try:
                action = OverrideAction(override["action"])
                date = datetime.fromisoformat(override["date"])
            except (KeyError, TypeError, ValueError):
                ctx.fail(file, f"exception de planning invalide : {override!r}")
                continue
            replacement = _schedule_target(ctx, file, override.get("replacement")) if action == OverrideAction.replaced else None
            overrides.append((override.get("uid"), date, action, replacement))
        # Reconnaissance : `uid`, à défaut la même programmation (cible, type, date ou récurrence) : les `id` restent.
        schedule = by_uid.get(entry.get("uid")) if is_uid(entry.get("uid"), "sch") else None
        if schedule is None:
            schedule = next((s for s in unused if _signature(s) == _signature(wanted)), None)
        if schedule is None:
            schedule = wanted
            ctx.db.add(schedule)
            if is_uid(entry.get("uid"), "sch") and not ctx.db.query(Schedule).filter(Schedule.uid == entry["uid"]).first() \
                    and all(entry["uid"] != other.uid for other in kept):
                schedule.uid = entry["uid"]
        else:
            unused = [s for s in unused if s is not schedule]
            schedule.target_type, schedule.target_id = wanted.target_type, wanted.target_id
            schedule.schedule_type, schedule.run_at, schedule.recurrence_rule = wanted.schedule_type, wanted.run_at, wanted.recurrence_rule
            schedule.active = wanted.active
        _sync_overrides(ctx, schedule, overrides)
        kept.append(schedule)
    removed_ids = [s.id for s in unused]
    for old in unused:
        ctx.db.delete(old)

    async def resync(db: Session) -> None:
        from app.scheduling.jobs import remove_schedule_job, sync_schedule_job

        for schedule_id in removed_ids:
            remove_schedule_job(schedule_id)
        for schedule in db.query(Schedule).filter(Schedule.channel == channel).all():
            sync_schedule_job(schedule)

    ctx.effects.append(resync)


def _sync_overrides(ctx: _Context, schedule: Schedule, wanted: list) -> None:
    """Exceptions reconnues par `uid`, à défaut par date ; les `id` et `uid` restent, le reste est créé ou supprimé."""
    from app.scheduling.occurrences import ensure_utc

    current = list(schedule.overrides) if schedule.id is not None else []
    by_uid = {o.uid: o for o in current}
    unused = list(current)
    for uid, date, action, replacement in wanted:
        match = by_uid.get(uid) if is_uid(uid, "ovr") else None
        if match is None:
            match = next((o for o in unused if ensure_utc(o.occurrence_date).date() == ensure_utc(date).date()), None)
        fields = dict(
            occurrence_date=date, action=action,
            replacement_target_type=replacement[0] if replacement else None,
            replacement_target_id=replacement[1] if replacement else None,
        )
        if match is None:
            override = ScheduleOverride(**fields)
            if is_uid(uid, "ovr") and uid not in by_uid and not ctx.db.query(ScheduleOverride).filter(ScheduleOverride.uid == uid).first():
                override.uid = uid
            schedule.overrides.append(override)
        else:
            unused = [o for o in unused if o is not match]
            for key, value in fields.items():
                setattr(match, key, value)
    for old in unused:
        schedule.overrides.remove(old)


# --- métadonnées des médias (library/) : jamais de création ni de suppression -----------------------------------------

def _text(ctx: _Context, file: str, label: str, value: Any, *, required: bool = False) -> tuple[bool, str | None]:
    """(valide, valeur nettoyée) : une chaîne vide efface un champ facultatif ; un champ obligatoire ne peut pas l'être."""
    if value is None and not required:
        return True, None
    if not isinstance(value, str):
        ctx.fail(file, f"{label} doit être un texte : {value!r}")
        return False, None
    value = value.strip()
    if required and not value:
        ctx.fail(file, f"{label} ne peut pas être vide")
        return False, None
    return True, value or None


def _integer(ctx: _Context, file: str, label: str, value: Any) -> tuple[bool, int | None]:
    if value is None:
        return True, None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        ctx.fail(file, f"{label} doit être un entier positif : {value!r}")
        return False, None
    return True, value


def _media(ctx: _Context, file: str, model, entry: Any, what: str, by_file: Callable[[Any], str | None], *, key=None):
    """Média existant désigné par `uid`, à défaut par son nom de fichier ; erreur s'il est introuvable ou ambigu."""
    if not isinstance(entry, dict):
        ctx.fail(file, f"{what} invalide : {entry!r}")
        return None
    found = _by_uid(ctx, model, entry)
    if found is not None:
        return found
    wanted = entry.get("file")
    candidates = [m for m in ctx.db.query(model).all() if wanted and by_file(m) and Path(by_file(m)).name == wanted]
    if len(candidates) == 1:
        return candidates[0]
    ctx.fail(file, f"{what} {'introuvable' if not candidates else 'ambigu'} (uid ou fichier requis, aucun média n'est créé) : {entry.get('title')!r}")
    return None


def _apply_library_videos(ctx: _Context, file: str, document: dict) -> None:
    from app.api.routes.videos import rename_video_file

    for entry in _list(ctx, file, document, "videos"):
        video = _media(ctx, file, Video, entry, "vidéo", lambda v: v.file_path)
        if video is None:
            continue
        if "title" in entry:
            ok, title = _text(ctx, file, f"titre de la vidéo {entry.get('uid') or entry.get('file')}", entry["title"], required=True)
            if ok and title != video.title:
                video.title = title
                video_id, new_title = video.id, title

                async def rename(db: Session, video_id=video_id, new_title=new_title) -> None:
                    # Le fichier physique suit le titre comme dans l'interface, mais seulement une fois la transaction validée.
                    target = db.get(Video, video_id)
                    if target is not None:
                        rename_video_file(target, new_title)
                        db.commit()

                ctx.effects.append(rename)
        for field in ("program", "release", "description"):
            if field in entry:
                ok, value = _text(ctx, file, f"« {field} » de la vidéo {entry.get('uid') or entry.get('file')}", entry[field])
                if ok:
                    setattr(video, field, value)


def _apply_library_backgrounds(ctx: _Context, file: str, document: dict) -> None:
    for entry in _list(ctx, file, document, "backgrounds"):
        background = _media(ctx, file, Background, entry, "fond", lambda b: b.file_path)
        if background is not None and "title" in entry:
            ok, title = _text(ctx, file, "titre du fond", entry["title"], required=True)
            if ok:
                background.title = title


def _apply_library_audio(ctx: _Context, file: str, document: dict) -> None:
    for entry in _list(ctx, file, document, "courses"):
        course = _by_uid(ctx, AudioCourse, entry) if isinstance(entry, dict) else None
        if course is None and isinstance(entry, dict):
            candidates = ctx.db.query(AudioCourse).filter(AudioCourse.title == entry.get("title")).all()
            if len(candidates) == 1:
                course = candidates[0]
        if course is None:
            ctx.fail(file, f"cours audio introuvable (uid ou titre actuel requis, aucun cours n'est créé) : {(entry or {}).get('title') if isinstance(entry, dict) else entry!r}")
            continue
        if "title" in entry:
            ok, title = _text(ctx, file, "titre du cours audio", entry["title"], required=True)
            if ok:
                course.title = title
        for field in ("program", "release"):
            if field in entry:
                ok, value = _text(ctx, file, f"« {field} » du cours « {course.title} »", entry[field])
                if ok:
                    setattr(course, field, value)
        for track_entry in entry.get("tracks") or []:
            track = _media(ctx, file, AudioTrack, track_entry, "piste", lambda t: t.file_path)
            if track is None:
                continue
            if "title" in track_entry:
                ok, title = _text(ctx, file, "titre de la piste", track_entry["title"], required=True)
                if ok:
                    track.title = title
            if "number" in track_entry:
                ok, number = _integer(ctx, file, f"« number » de la piste {track.uid}", track_entry["number"])
                if ok and number is not None:
                    track.number = number


def _apply_library_radio(ctx: _Context, file: str, document: dict) -> None:
    for entry in _list(ctx, file, document, "tracks"):
        track = _media(ctx, file, RadioTrack, entry, "morceau", lambda t: t.file_path)
        if track is None:
            continue
        if "title" in entry:
            ok, title = _text(ctx, file, f"titre du morceau {track.uid}", entry["title"], required=True)
            if ok:
                track.title = title
        for field in ("artist", "album", "album_artist", "genre"):
            if field in entry:
                ok, value = _text(ctx, file, f"« {field} » du morceau {track.uid}", entry[field])
                if ok:
                    setattr(track, field, value)
        for field in ("track_number", "disc_number", "year"):
            if field in entry:
                ok, value = _integer(ctx, file, f"« {field} » du morceau {track.uid}", entry[field])
                if ok:
                    setattr(track, field, value)


APPLIERS: dict[str, Callable[[_Context, str, dict], None]] = {
    "settings.json": _apply_settings,
    "outputs/display.json": _apply_display_outputs,
    "outputs/radio.json": _apply_radio_outputs,
    "library/videos.json": _apply_library_videos,
    "library/audio.json": _apply_library_audio,
    "library/radio.json": _apply_library_radio,
    "library/backgrounds.json": _apply_library_backgrounds,
    "library/announcements.json": _apply_announcements,
    "playlists/video.json": _apply_video_playlists,
    "playlists/audio.json": _apply_audio_playlists,
    "playlists/radio.json": _apply_radio_playlists,
    "radio/tags.json": _apply_radio_tags,
    "radio/announcement-rules.json": _apply_announcement_rules,
    **{config_files.schedule_path(c): (lambda ctx, f, d, c=c: _apply_schedule(ctx, f, d, c))
       for c in config_files.SCHEDULE_CHANNELS},
    "machine.json": _apply_machine,
}
# Ordre d'application : les métadonnées des médias et les playlists avant ce qui les cite. `outputs/radio.json` vient
# après `playlists/radio.json` : son ambiance par défaut se désigne par un nom ou un `uid`, qui doit déjà exister (ou
# venir d'être créé dans la même transaction).
ORDER = [
    "settings.json",
    "outputs/display.json",
    "library/videos.json",
    "library/audio.json",
    "library/radio.json",
    "library/backgrounds.json",
    "library/announcements.json",
    "playlists/video.json",
    "playlists/audio.json",
    "playlists/radio.json",
    "outputs/radio.json",
    "radio/tags.json",
    "radio/announcement-rules.json",
    *[config_files.schedule_path(channel) for channel in config_files.SCHEDULE_CHANNELS],
    "machine.json",
]


def _strip_uids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_uids(v) for k, v in value.items() if k != "uid"}
    if isinstance(value, list):
        return [_strip_uids(v) for v in value]
    return value


def _without_links(document: dict) -> dict:
    links = ("chapters", "chapters_source", "chapters_file", "subtitles", "subtitle_files")
    return {**document, "videos": [{k: v for k, v in entry.items() if k not in links} if isinstance(entry, dict) else entry
                                  for entry in document.get("videos") or []]}


def _diff(name: str, before: dict, wanted: dict) -> list[str]:
    ignored = ("warnings", "prune", "schema")
    clean = {k: v for k, v in wanted.items() if k not in ignored}
    current = {k: v for k, v in before.items() if k not in ignored}
    if name == "library/videos.json":
        # Liens vers les chapitres et sous-titres : informatifs, jamais appliqués, donc absents de l'écart.
        clean, current = _without_links(clean), _without_links(current)
    if '"uid"' not in json.dumps(clean):
        # Document de la version 5.1, sans `uid` : l'écart ne porte pas sur les identifiants.
        current = _strip_uids(current)
    if clean == current:
        return []
    return list(difflib.unified_diff(
        config_files.dumps(current).splitlines(), config_files.dumps(clean).splitlines(),
        fromfile=f"actuel/{name}", tofile=f"demandé/{name}", lineterm="", n=1,
    ))


async def apply(db: Session, files: dict[str, Any], *, dry_run: bool, include_machine: bool) -> dict[str, Any]:
    """Valide et applique `{nom de fichier: document}` ; lève `ConfigErrors` (rien n'est écrit) si un élément est
    invalide. Renvoie l'écart par fichier, ce qui a été ignoré et ce qui demande un redémarrage. La validation et
    l'écriture tournent hors de la boucle d'événements : un gros document ne fige ni les flux ni les écrans ; seuls
    les effets à chaud (diffusions, moteurs) reviennent sur la boucle."""
    result, effects = await run_in_threadpool(_validate_and_write, db, files, dry_run, include_machine)
    for effect in effects:
        await effect(db)
    if not dry_run:
        config_files.schedule_mirror()
    return result


def _validate_and_write(
    db: Session, files: dict[str, Any], dry_run: bool, include_machine: bool,
) -> tuple[dict[str, Any], list[Callable[[Session], Awaitable[None]]]]:
    renamed: dict[str, Any] = {}
    errors = []
    for key, document in files.items():
        name = config_files.canonical_name(str(key))
        if name == "manifest.json":
            continue  # index de l'export : rien à appliquer
        if name in renamed:
            errors.append(f"{name} fourni deux fois (nom plat et arborescence)")
        renamed[name] = document
    files = renamed
    errors += [f"fichier inconnu : {name}" for name in sorted(set(files) - set(APPLIERS))]
    if errors:
        raise ConfigErrors(errors)
    ctx = _Context(db)
    skipped = []
    changes: dict[str, list[str]] = {}
    for name in ORDER:
        if name not in files:
            continue
        document = files[name]
        if name == "machine.json" and not include_machine:
            skipped.append(name)
            continue
        if not isinstance(document, dict) or document.get("schema") not in config_files.ACCEPTED_SCHEMAS:
            ctx.fail(name, f"« schema » doit valoir {' ou '.join(map(str, config_files.ACCEPTED_SCHEMAS))}")
            continue
        if document.get("kind") != config_files.KINDS[name]:
            ctx.fail(name, f"« kind » doit valoir {config_files.KINDS[name]}")
            continue
        changes[name] = _diff(name, config_files.BUILDERS[name](db), document)
        with db.no_autoflush:
            try:
                APPLIERS[name](ctx, name, document)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError, SQLAlchemyError) as exc:
                # Un document JSON mal typé (liste au lieu d'objet, chaîne au lieu d'entier...) est une erreur de
                # validation : il ne doit jamais produire un 500. La transaction est annulée plus bas comme pour
                # toute autre erreur.
                ctx.fail(name, f"document invalide : {exc}")
        if not ctx.errors:
            # Rendus visibles dans la transaction (non validée) : un fichier suivant peut citer ce qui vient d'être créé.
            try:
                db.flush()
            except Exception as exc:
                ctx.fail(name, f"écriture refusée par la base : {exc}")
    if ctx.errors:
        db.rollback()
        raise ConfigErrors(ctx.errors)
    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        raise ConfigErrors([f"écriture refusée par la base : {exc}"]) from exc
    if dry_run:
        db.rollback()
    else:
        db.commit()
    result = {
        "applied": not dry_run,
        "changes": {name: lines for name, lines in changes.items() if lines},
        "skipped": skipped,
        "restart_required": sorted(set(ctx.restart_required)),
    }
    return result, ([] if dry_run else ctx.effects)

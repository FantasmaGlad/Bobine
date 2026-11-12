"""Radio : sorties, playlists, étiquettes, annonces et règles d'annonce."""
from __future__ import annotations
import json
from sqlalchemy.orm import Session
from app.utils.uid import is_uid
from app.models import (
    RadioAnnouncement, RadioAnnouncementRule, RadioAnnouncementRuleType, RadioPlaylist, RadioPlaylistItem, RadioTag,
)
from app.config_apply.apply_playlists import _prune, _replace_playlist
from app.config_apply.apply_settings import _write_setting
from app.config_apply.context import _Context, _by_uid, _claim_uid, _pick
from app.config_apply.resolve import _radio_track, _unique_by_name
from app.config_apply.values import _TIME_RE, _flag, _list, _names


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

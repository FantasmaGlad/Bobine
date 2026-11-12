"""Playlists vidéo et audio, suppression des absentes (`prune`)."""
from __future__ import annotations
from app.models import (
    AudioPlaylist, AudioPlaylistItem, Playlist, PlaylistItem,
    RadioPlaylist, ScheduleTargetType,
)
from app.scheduling.targets import drop_schedules_targeting
from app.config_apply.apply_schedule import _resync_all_schedules
from app.config_apply.context import _Context, _by_uid, _claim_uid
from app.config_apply.resolve import _audio_track, _background, _unique_by_name, _video
from app.config_apply.values import _list, _names


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
        drop_schedules_targeting(ctx.db, target, removed_ids)
        ctx.effects.append(_resync_all_schedules(None))


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

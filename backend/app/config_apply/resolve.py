"""Résolution des références d'un fichier (vidéos, fonds, pistes, morceaux) vers les objets de la base."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
from app.models import (
    AudioCourse, AudioTrack, Background, RadioTrack, Video,
)
from app.config_apply.context import _Context, _by_uid, _pick


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
    found = ctx.db.query(model).filter(model.name == name).all()
    if len(found) > 1:
        ctx.fail(file, f"plusieurs playlists « {name} » existent : renommez-en une avant d'appliquer")
    return found[0] if len(found) == 1 else None


def _media(ctx: _Context, file: str, model, entry: Any, what: str, by_file: Callable[[Any], str | None], *, key=None):
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

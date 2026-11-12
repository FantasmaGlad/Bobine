"""Métadonnées des médias existants (`library/`)."""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models import (
    AudioCourse, AudioTrack, Background, RadioTrack, Video,
)
from app.config_apply.context import _Context, _by_uid
from app.config_apply.resolve import _media
from app.config_apply.values import _integer, _list, _text


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

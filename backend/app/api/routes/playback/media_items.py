"""Description des médias envoyée aux moteurs : cours audio, pistes, vidéos d'une playlist."""

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.models import (
    AudioCourse,
    Background,
)
from app.utils.importer.formats import is_image_background


def _thumbnail_filename(thumbnail_path: str | None) -> str | None:
    """Nom de fichier seul (pas le chemin disque complet) pour reconstruire
    l'URL `/api/thumbnails/<fichier>` côté client.3 vignette du
    bloc « En direct »."""
    return thumbnail_path.split("/")[-1] if thumbnail_path else None


def _build_audio_course_item(course: AudioCourse, db: Session) -> dict:
    """Forme attendue par PlaybackManager.load_audio_course/load_audio_playlist
    pour UN cours audio : pistes triées + fond d'ambiance résolu (par piste ou par repli cours/défaut)."""
    background_title = None
    background_is_image = False
    effective_bg_id = course.background_id
    if not effective_bg_id:
        from app.models import Setting
        default_setting = db.query(Setting).filter(Setting.key == "default_coach_background_id").first()
        if default_setting and default_setting.value and default_setting.value.isdigit():
            effective_bg_id = int(default_setting.value)

    if effective_bg_id:
        bg = db.query(Background).filter(Background.id == effective_bg_id).first()
        if bg:
            background_title = bg.title
            background_is_image = is_image_background(bg.file_path)
        else:
            effective_bg_id = None

    tracks = []
    for t in sorted(course.tracks, key=lambda t: t.position):
        if not t.available:
            continue  # piste d'un support externe débranché : sautée
        track_bg_id = getattr(t, "background_id", None)
        track_bg_title = None
        track_bg_is_image = False
        if track_bg_id:
            track_bg = db.query(Background).filter(Background.id == track_bg_id).first()
            if track_bg:
                track_bg_title = track_bg.title
                track_bg_is_image = is_image_background(track_bg.file_path)
            else:
                track_bg_id = None

        final_bg_id = track_bg_id if track_bg_id is not None else effective_bg_id
        final_bg_title = track_bg_title if track_bg_id is not None else background_title
        final_bg_is_image = track_bg_is_image if track_bg_id is not None else background_is_image

        tracks.append({
            "id": t.id,
            "number": t.number,
            "title": t.title,
            "duration_seconds": t.duration_seconds,
            "background_id": final_bg_id,
            "background_title": final_bg_title,
            "background_is_image": final_bg_is_image,
        })

    return {
        "id": course.id,
        "title": course.title,
        "program": course.program,
        "background_id": effective_bg_id,
        "background_title": background_title,
        "background_is_image": background_is_image,
        "tracks": tracks,
    }


def _build_audio_playlist_tracks(audio_playlist) -> list[dict]:
    """Forme attendue par PlaybackManager.load_audio_playlist pour une
    playlist audio — traverse `items`/`item.track`/`item.background`
    (relations ORM paresseuses) : fonction SYNCHRONE, à appeler via
    `run_in_threadpool`."""
    sorted_items = sorted(audio_playlist.items, key=lambda item: item.position)
    return [
        {
            "id": item.track.id,
            "number": item.track.number,
            "title": item.track.title,
            "duration_seconds": item.track.duration_seconds,
            # Fond d'ambiance propre à CETTE piste : résolu une fois ici plutôt
            # que par le kiosk, comme le fond du cours/playlist lui-même.
            "background_id": item.background_id,
            "background_title": item.background.title if item.background else None,
            "background_is_image": is_image_background(item.background.file_path) if item.background else False,
        }
        for item in sorted_items
        if item.track.available  # piste d'un support externe débranché : sautée
    ]


def _build_playlist_video_items(playlist) -> list[dict]:
    """Même rôle que `_build_audio_playlist_tracks` ci-dessus, pour une
    playlist VIDÉO (`item.video`, relation ORM paresseuse) — fonction
    SYNCHRONE, à appeler via `run_in_threadpool`."""
    sorted_items = sorted(playlist.items, key=lambda x: x.position)
    return [
        {
            "id": item.video.id,
            "title": item.video.title,
            "duration_seconds": item.video.duration_seconds,
            "program": item.video.program,
            "release": item.video.release,
            "thumbnail_url": _thumbnail_filename(item.video.thumbnail_path),
            "description": item.video.description,
            "audio_channels": item.video.audio_channels,
            "audio_codec": item.video.audio_codec,
            "fps": item.video.fps,
            "bitrate_kbps": item.video.bitrate_kbps,
            "storage_id": item.video.storage_id,
            "width": item.video.width,
            "height": item.video.height,
        }
        for item in sorted_items
        if item.video.available  # support externe débranché : élément sauté
    ]


async def _load_audio_course_into_manager(course: AudioCourse, manager, db: Session, chain_mode=None, chain_timer_seconds=None, client_ts=None):
    # la construction de
    # cet item traverse des relations ORM (background) qui peuvent
    # déclencher leurs propres requêtes paresseuses — regroupées ici dans
    # un seul aller-retour au threadpool plutôt que plusieurs micro-appels.
    item = await run_in_threadpool(_build_audio_course_item, course, db)
    await manager.load_audio_course(
        item["id"], item["title"], item["program"], item["background_id"], item["tracks"],
        chain_mode=chain_mode, chain_timer_seconds=chain_timer_seconds, client_ts=client_ts,
        background_title=item["background_title"], background_is_image=item["background_is_image"],
    )

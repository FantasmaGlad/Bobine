"""Description d'une vidéo transmise aux moteurs de lecture."""


def thumbnail_filename(thumbnail_path: str | None) -> str | None:
    return thumbnail_path.split("/")[-1] if thumbnail_path else None


def video_details(video) -> dict:
    return {
        "release": video.release,
        "thumbnail_url": thumbnail_filename(video.thumbnail_path),
        "description": video.description,
        "audio_channels": video.audio_channels,
        "audio_codec": video.audio_codec,
        "fps": video.fps,
        "bitrate_kbps": video.bitrate_kbps,
        "width": video.width,
        "height": video.height,
    }


def video_item(video) -> dict:
    return {
        "id": video.id,
        "title": video.title,
        "duration_seconds": video.duration_seconds,
        "program": video.program,
        "storage_id": video.storage_id,
        **video_details(video),
    }


def playlist_video_items(playlist) -> list[dict]:
    return [video_item(item.video) for item in sorted(playlist.items, key=lambda item: item.position) if item.video.available]

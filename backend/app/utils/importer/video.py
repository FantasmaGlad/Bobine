"""Import d'une vidéo de cours."""
from pathlib import Path

from app.config import settings
from app.models import ImportSource, Video
from app.utils.importer.naming import parse_title_program_release
from app.utils.importer.pipeline import Target, import_media, wait_if_watched

_VIDEO = Target(directory=lambda: settings.media_dir, prefix="video", label="Vidéo")
_META_FIELDS = ("width", "height", "codec", "description", "audio_channels", "audio_codec", "fps", "bitrate_kbps", "pix_fmt")


def import_video(src_path: str, original_filename: str, source: ImportSource, job_id: str | None = None) -> Video:
    """Importe une vidéo : attente de copie, sonde, normalisation si besoin, miniature, enregistrement."""
    wait_if_watched(src_path, original_filename, source)
    title, program, release = parse_title_program_release(original_filename)

    def build(dest: Path, meta: dict, thumbnail: str | None) -> Video:
        return Video(file_path=str(dest), title=title, program=program, release=release, source=source,
                     duration_seconds=meta.get("duration_seconds"), thumbnail_path=thumbnail,
                     **{field: meta.get(field) for field in _META_FIELDS})

    origin = "téléversement" if source == ImportSource.upload else "dossier surveillé"
    return import_media(src_path, original_filename, source, job_id, _VIDEO, settings.thumbnails_dir, build,
                        "video_imported", lambda video: f"{video.title} ({origin})")

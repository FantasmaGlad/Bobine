"""Métadonnées d'un média importé, avec repli quand ffprobe échoue."""
import logging
from pathlib import Path
from app.utils.video_utils.probe import extract_metadata
from app.utils.video_utils.container import read_mp4_duration_seconds


logger = logging.getLogger(__name__)


def extract_metadata_or_unknown(file_path: str, original_filename: str) -> dict:
    """Enveloppe extract_metadata() pour ne plus faire échouer tout l'import quand ffprobe est indisponible ou en erreur."""
    try:
        return extract_metadata(file_path)
    except Exception as e:
        logger.error(
            f"ffprobe indisponible ou en echec pour {original_filename} - import "
            f"poursuivi sans metadonnees (duree/resolution/codec inconnus, "
            f"detection DRM impossible) : {e}"
        )
        duration = None
        if Path(file_path).suffix.lower() in (".mp4", ".m4v"):
            duration = read_mp4_duration_seconds(file_path)
        return {
            "duration_seconds": duration,
            "width": None,
            "height": None,
            "codec": None,
            "audio_codec": None,
            "audio_channels": None,
            "fps": None,
            "bitrate_kbps": None,
            "pix_fmt": None,
            "description": None,
            "is_drm": False,
        }

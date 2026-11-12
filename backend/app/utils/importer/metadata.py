"""Métadonnées d'un média importé, avec repli quand ffprobe échoue."""
import logging
from pathlib import Path
from app.utils.video_utils.probe import extract_metadata
from app.utils.video_utils.container import read_mp4_duration_seconds


logger = logging.getLogger(__name__)


def extract_metadata_or_unknown(file_path: str, original_filename: str) -> dict:
    """Enveloppe extract_metadata() pour ne plus faire échouer tout l'import
    quand ffprobe est indisponible ou en erreur (sous Android : aucun binaire ffprobe utilisable
    sous Android, tout binaire lie glibc statique y est tue par le filtre
    seccomp). Duree/largeur/hauteur/codec/miniature sont deja nullables en
    base et deja tolerees partout en aval (check_compatibility traite un
    codec/audio_codec absent comme compatible, generate_thumbnail a son
    propre echec tolere dans import_video/import_background) - seule la
    detection DRM ne peut alors plus s'executer (is_drm forcee a False),
    seul compromis reel de ce mode degrade.

    Repli supplementaire : pour un MP4/M4V, la duree reste recuperable sans ffprobe
    via un parcours pur Python de l'atome 'mvhd' (read_mp4_duration_seconds) -
    largeur/hauteur/codec restent None (demanderaient de decoder 'stsd',
    hors de portee de ce repli minimal).
    """
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

"""Ce qu'il faut faire d'un média importé pour qu'il soit lisible partout (aucun, remux, transcodage)."""
from pathlib import Path
from app.utils.video_utils.container import is_faststart_mp4


COMPATIBLE_VIDEO_CODECS = {"h264"}


COMPATIBLE_COURSE_VIDEO_CODECS = COMPATIBLE_VIDEO_CODECS | {"hevc", "vp9"}


def check_compatibility(metadata: dict, file_path: str, strict_video_codec: bool = False) -> dict:
    """Vérifie la compatibilité de la vidéo par rapport aux règles de lecture directe du navigateur."""
    if metadata["is_drm"]:
        return {
            "is_compatible": False,
            "needs_normalization": False,
            "actions": [],
            "error": "Le fichier vidéo est protégé par DRM (FairPlay, etc.) et ne peut pas être lu."
        }

    ext = Path(file_path).suffix.lower()
    is_mp4_container = ext in (".mp4", ".m4v")
    is_audio_compatible = metadata["audio_codec"] is None or metadata["audio_codec"] == "aac"
    allowed_video_codecs = COMPATIBLE_VIDEO_CODECS if strict_video_codec else COMPATIBLE_COURSE_VIDEO_CODECS
    is_video_codec_compatible = metadata["codec"] is None or metadata["codec"] in allowed_video_codecs

    needs_audio_recode = metadata["audio_codec"] is not None and metadata["audio_codec"] != "aac"
    needs_container_recode = not is_mp4_container
    needs_video_recode = not is_video_codec_compatible
    needs_faststart_remux = (
        is_mp4_container and metadata.get("codec") is not None and not is_faststart_mp4(file_path)
    )

    actions = []
    if needs_video_recode:
        actions.append("recode_video")
    if needs_audio_recode:
        actions.append("recode_audio")
    if needs_container_recode:
        actions.append("recode_container")
    if needs_faststart_remux and not needs_container_recode:
        actions.append("remux_faststart")

    is_compatible = is_mp4_container and is_audio_compatible and is_video_codec_compatible

    return {
        "is_compatible": is_compatible,
        "needs_normalization": len(actions) > 0,
        "actions": actions,
        "error": None
    }

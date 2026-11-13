"""Lecture des métadonnées d'un média par ffprobe."""
import subprocess
import json
import logging
from app.utils.ffmpeg_binaries import (
    FFPROBE_BIN,
    is_missing_tool_error,
    media_subprocess_kwargs,
    missing_tool_error,
)
from app.utils.video_utils.limits import FFPROBE_TIMEOUT_SECONDS


logger = logging.getLogger(__name__)


def get_video_info(file_path: str) -> dict:
    """Exécute ffprobe pour extraire les informations de flux et de format de la vidéo au format JSON."""
    cmd = [
        FFPROBE_BIN,
        "-v", "error",
        "-show_entries", "format=duration",
        "-show_streams",
        "-print_format", "json",
        file_path
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=FFPROBE_TIMEOUT_SECONDS,
            **media_subprocess_kwargs(),
        )
        return json.loads(res.stdout)
    except subprocess.TimeoutExpired:
        logger.error(f"ffprobe : délai dépassé ({FFPROBE_TIMEOUT_SECONDS}s) pour {file_path}")
        raise ValueError(f"L'analyse du fichier vidéo a dépassé {FFPROBE_TIMEOUT_SECONDS}s (ffprobe)")
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe failed for {file_path}: {e.stderr}")
        raise ValueError(f"Impossible de lire le fichier vidéo avec ffprobe : {e.stderr}")
    except OSError as e:
        if is_missing_tool_error(e):
            missing = missing_tool_error("ffprobe", e)
            logger.error(f"ffprobe ne peut pas être lancé ({FFPROBE_BIN}) : {e}")
            raise missing from e
        logger.error(f"Error running ffprobe for {file_path}: {e}")
        raise ValueError(f"Erreur lors de la lecture des métadonnées : {str(e)}")
    except Exception as e:
        logger.error(f"Error running ffprobe for {file_path}: {e}")
        raise ValueError(f"Erreur lors de la lecture des métadonnées : {str(e)}")


def _number(raw, cast=float):
    try:
        return cast(raw) if raw is not None else None
    except (ValueError, TypeError):
        return None


def _rate(raw: str | None) -> float | None:
    if not raw or raw == "0/0":
        return None
    try:
        if "/" in raw:
            num, den = raw.split("/", 1)
            value = float(num) / float(den) if float(den) > 0 else None
        else:
            value = float(raw)
    except (ValueError, ZeroDivisionError):
        return None
    return round(value, 2) if value is not None and 1 <= value <= 240 else None


def _description(*tag_sets) -> str | None:
    for tags in tag_sets:
        if not isinstance(tags, dict):
            continue
        lower = {str(k).lower(): str(v) for k, v in tags.items()}
        candidate = lower.get("description") or lower.get("comment") or lower.get("synopsis")
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def _is_drm(streams: list[dict]) -> bool:
    for stream in streams:
        if {str(stream.get("codec_name", "")).lower(), str(stream.get("codec_tag_string", "")).lower()} & {"encv", "enca"}:
            return True
    return any("encryption" in k.lower() or "drm" in k.lower() for stream in streams for k in stream.get("tags", {}))


def extract_metadata(file_path: str) -> dict:
    """Extrait les métadonnées pertinentes (durée, résolution, codecs, DRM) du fichier vidéo."""
    info = get_video_info(file_path)
    streams = info.get("streams", [])
    fmt = info.get("format", {})
    video = next((s for s in streams if s.get("codec_type") == "video"), None) or {}
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None) or {}
    duration = _number(fmt.get("duration"))
    if duration is None:
        duration = _number(video.get("duration"))
    bitrate = _number(fmt.get("bit_rate") or video.get("bit_rate") or None, int)
    return {
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "audio_channels": _number(audio.get("channels"), int),
        "fps": next((r for r in (_rate(video.get(k)) for k in ("r_frame_rate", "avg_frame_rate")) if r is not None), None),
        "bitrate_kbps": bitrate // 1000 if bitrate is not None else None,
        "pix_fmt": video.get("pix_fmt"),
        "description": _description(fmt.get("tags") or {}, video.get("tags") or {}),
        "is_drm": _is_drm(streams),
    }

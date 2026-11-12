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


def extract_metadata(file_path: str) -> dict:
    """Extrait les métadonnées pertinentes (durée, résolution, codecs, DRM) du fichier vidéo."""
    info = get_video_info(file_path)
    streams = info.get("streams", [])
    fmt = info.get("format", {})

    duration = None
    if "duration" in fmt:
        try:
            duration = float(fmt["duration"])
        except ValueError:
            pass

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = None
    height = None
    v_codec = None
    pix_fmt = None
    if v_stream:
        width = v_stream.get("width")
        height = v_stream.get("height")
        v_codec = v_stream.get("codec_name")
        pix_fmt = v_stream.get("pix_fmt")
        if duration is None and "duration" in v_stream:
            try:
                duration = float(v_stream["duration"])
            except ValueError:
                pass

    a_codec = None
    audio_channels = None
    if a_stream:
        a_codec = a_stream.get("codec_name")
        channels_val = a_stream.get("channels")
        if channels_val is not None:
            try:
                audio_channels = int(channels_val)
            except (ValueError, TypeError):
                pass

    fps = None
    if v_stream:
        for rate_key in ("r_frame_rate", "avg_frame_rate"):
            raw_rate = v_stream.get(rate_key)
            if raw_rate and raw_rate != "0/0":
                try:
                    if "/" in raw_rate:
                        num, den = raw_rate.split("/", 1)
                        d = float(den)
                        if d > 0:
                            val = float(num) / d
                            if 1 <= val <= 240:
                                fps = round(val, 2)
                                break
                    else:
                        val = float(raw_rate)
                        if 1 <= val <= 240:
                            fps = round(val, 2)
                            break
                except (ValueError, ZeroDivisionError):
                    pass

    bitrate_kbps = None
    raw_br = fmt.get("bit_rate") or (v_stream.get("bit_rate") if v_stream else None)
    if raw_br:
        try:
            bitrate_kbps = int(raw_br) // 1000
        except (ValueError, TypeError):
            pass

    description = None
    fmt_tags = fmt.get("tags") or {}
    if isinstance(fmt_tags, dict):
        lower_tags = {str(k).lower(): str(v) for k, v in fmt_tags.items()}
        desc_candidate = lower_tags.get("description") or lower_tags.get("comment") or lower_tags.get("synopsis")
        if desc_candidate and desc_candidate.strip():
            description = desc_candidate.strip()

    if not description and v_stream:
        v_tags = v_stream.get("tags") or {}
        if isinstance(v_tags, dict):
            lower_vtags = {str(k).lower(): str(v) for k, v in v_tags.items()}
            desc_candidate = lower_vtags.get("description") or lower_vtags.get("comment") or lower_vtags.get("synopsis")
            if desc_candidate and desc_candidate.strip():
                description = desc_candidate.strip()

    is_drm = False
    for s in streams:
        c_name = str(s.get("codec_name", "")).lower()
        c_tag = str(s.get("codec_tag_string", "")).lower()
        if c_name in ("encv", "enca") or c_tag in ("encv", "enca"):
            is_drm = True
            break

    if not is_drm:
        for s in streams:
            for k, v in s.get("tags", {}).items():
                if "encryption" in k.lower() or "drm" in k.lower():
                    is_drm = True
                    break
            if is_drm:
                break

    return {
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "codec": v_codec,
        "audio_codec": a_codec,
        "audio_channels": audio_channels,
        "fps": fps,
        "bitrate_kbps": bitrate_kbps,
        "pix_fmt": pix_fmt,
        "description": description,
        "is_drm": is_drm
    }

"""Utilitaires du module Radio."""
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from app.utils.ffmpeg_binaries import FFMPEG_BIN, FFPROBE_BIN, media_subprocess_kwargs, with_nostdin
from app.utils import media_formats

logger = logging.getLogger(__name__)

WEB_PLAYABLE_EXTENSIONS = media_formats.WEB_PLAYABLE_AUDIO
AUDIO_EXTENSIONS = media_formats.RADIO_AUDIO

AUDIO_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
}


def content_type_for(file_path: str) -> str:
    return AUDIO_CONTENT_TYPES.get(Path(file_path).suffix.lower(), "application/octet-stream")


def clean_filename_label(file_path: str) -> str:
    """Dérive un libellé lisible depuis un nom de fichier."""
    stem = Path(file_path).stem.replace("_", " ").strip()
    return stem or Path(file_path).stem


def needs_transcode(file_path: str) -> bool:
    return Path(file_path).suffix.lower() not in WEB_PLAYABLE_EXTENSIONS


def _first_tag(tags: dict, *keys: str) -> str | None:
    lowered = {k.lower(): v for k, v in tags.items()}
    for key in keys:
        val = lowered.get(key.lower())
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return None


def _leading_int(value: str | None) -> int | None:
    if not value:
        return None
    m = re.match(r"\s*0*(\d{1,4})", value)
    return int(m.group(1)) if m else None


def _year_from(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"(\d{4})", value)
    return int(m.group(1)) if m else None


def extract_radio_metadata(file_path: str) -> dict:
    """Métadonnées d'un morceau via ffprobe (tags de conteneur + du 1er flux audio fusionnés)."""
    meta: dict = {
        "title": None, "artist": None, "album": None, "album_artist": None,
        "track_number": None, "disc_number": None, "year": None, "genre": None,
        "duration_seconds": None,
    }
    cmd = [FFPROBE_BIN, "-v", "error", "-show_format", "-show_streams", "-of", "json", file_path]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, **media_subprocess_kwargs())
        info = json.loads(res.stdout)
    except Exception as e:
        logger.error(f"ffprobe a échoué pour le morceau radio {file_path}: {e}")
        info = {}

    fmt = info.get("format", {}) or {}
    tags = dict(fmt.get("tags", {}) or {})
    for stream in info.get("streams", []) or []:
        if stream.get("codec_type") == "audio":
            for k, v in (stream.get("tags", {}) or {}).items():
                tags.setdefault(k, v)
            break

    meta["title"] = _first_tag(tags, "title")
    meta["artist"] = _first_tag(tags, "artist", "author", "performer")
    meta["album"] = _first_tag(tags, "album")
    meta["album_artist"] = _first_tag(tags, "album_artist", "albumartist", "band")
    meta["track_number"] = _leading_int(_first_tag(tags, "track", "tracknumber"))
    meta["disc_number"] = _leading_int(_first_tag(tags, "disc", "discnumber", "disk"))
    meta["year"] = _year_from(_first_tag(tags, "date", "year", "originalyear", "creation_time"))
    meta["genre"] = _first_tag(tags, "genre")

    duration = fmt.get("duration")
    try:
        meta["duration_seconds"] = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        meta["duration_seconds"] = None

    if not meta["title"]:
        meta["title"] = clean_filename_label(file_path)

    return meta


def extract_embedded_cover(file_path: str, covers_dir: str, file_id: str) -> str | None:
    """Extrait la pochette embarquée (APIC / cover art) vers un JPEG redimensionné dans `covers_dir`."""
    Path(covers_dir).mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    try:
        cmd = [FFMPEG_BIN, "-y", "-i", file_path, "-an", "-vframes", "1", tmp.name]
        res = subprocess.run(with_nostdin(cmd), capture_output=True, **media_subprocess_kwargs())
        if res.returncode != 0 or not os.path.exists(tmp.name) or os.path.getsize(tmp.name) == 0:
            return None
        from PIL import Image
        dest = Path(covers_dir) / f"cover_{file_id}.jpg"
        with Image.open(tmp.name) as img:
            img = img.convert("RGB")
            img.thumbnail((600, 600))
            img.save(dest, "JPEG", quality=85)
        return str(dest)
    except Exception as e:
        logger.warning(f"Extraction de pochette échouée pour {file_path}: {e}")
        return None
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass


def save_cover_image(src_image_path: str, covers_dir: str, file_id: str) -> str:
    """Enregistre une pochette fournie manuellement (upload) : redimensionnée et normalisée en JPEG, comme les pochettes extraites."""
    Path(covers_dir).mkdir(parents=True, exist_ok=True)
    from PIL import Image
    dest = Path(covers_dir) / f"cover_{file_id}.jpg"
    with Image.open(src_image_path) as img:
        img = img.convert("RGB")
        img.thumbnail((600, 600))
        img.save(dest, "JPEG", quality=85)
    return str(dest)


def transcode_to_web(src_path: str, dest_path: str) -> None:
    """Transcode un format non lu par le navigateur."""
    cmd = [FFMPEG_BIN, "-y", "-i", src_path, "-vn", "-c:a", "aac", "-b:a", "256k", dest_path]
    res = subprocess.run(with_nostdin(cmd), capture_output=True, text=True, **media_subprocess_kwargs())
    if res.returncode != 0:
        raise RuntimeError(f"Transcodage échoué pour {src_path}: {res.stderr[-500:]}")


def _measure_loudnorm(src_path: str, target_lufs: float) -> dict | None:
    cmd = [
        FFMPEG_BIN, "-y", "-i", src_path, "-vn",
        "-af", f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    res = subprocess.run(with_nostdin(cmd), capture_output=True, text=True, **media_subprocess_kwargs())
    if res.returncode != 0:
        return None
    matches = re.findall(r"\{[^{}]*\}", res.stderr, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def normalize_announcement_loudness(src_path: str, dest_path: str, target_lufs: float = -10.0) -> None:
    """Normalise le loudness d'un rappel (filtre EBU R128 `loudnorm`) au niveau d'une musique commerciale, puis ré-encode en AAC/.m4a."""
    measured = _measure_loudnorm(src_path, target_lufs)
    if measured is not None:
        af = (
            f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
        )
    else:
        af = f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11"
    cmd = [
        FFMPEG_BIN, "-y", "-i", src_path, "-vn",
        "-af", af,
        "-c:a", "aac", "-b:a", "192k", dest_path,
    ]
    res = subprocess.run(with_nostdin(cmd), capture_output=True, text=True, **media_subprocess_kwargs())
    if res.returncode != 0:
        raise RuntimeError(f"Normalisation loudness échouée pour {src_path}: {res.stderr[-500:]}")

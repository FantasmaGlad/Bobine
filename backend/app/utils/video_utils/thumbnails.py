"""Miniatures des vidéos."""
import subprocess
import logging
import uuid
import time
from pathlib import Path
from app.utils.ffmpeg_binaries import (
    FFMPEG_BIN,
    is_missing_tool_error,
    media_subprocess_kwargs,
    missing_tool_error,
    with_nostdin,
)
from app.utils.video_utils.limits import FFMPEG_THUMBNAIL_TIMEOUT_SECONDS


logger = logging.getLogger(__name__)


def _initial_offset(duration: float | None) -> float:
    offset = max(1.0, duration * 0.1) if duration else 5.0
    if duration and offset >= duration:
        offset = duration * 0.1
    return offset


def _offsets(offset: float, duration: float | None) -> list[str]:
    tries = [str(offset)]
    if offset != 0.1:
        tries.append(str(0.0 if duration and 0.1 >= duration else 0.1))
    return [*tries, "0.0"]


def _command(video_path: str, offset: str, thumb_path: Path) -> list[str]:
    return [FFMPEG_BIN, "-ss", offset, "-i", video_path, "-vframes", "1", "-q:v", "2", "-strict", "-2", "-update", "1", "-y", str(thumb_path)]


def _produced(cmd: list[str], thumb_path: Path) -> bool:
    subprocess.run(
        with_nostdin(cmd), capture_output=True, text=True, check=True,
        timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS, **media_subprocess_kwargs(),
    )
    return thumb_path.exists() and thumb_path.stat().st_size > 0


def _retry_with_av1_decoder(cmd: list[str], thumb_path: Path) -> bool:
    try:
        return _produced([FFMPEG_BIN, "-operating_rate", "1000", "-c:v", "av1_mediacodec", *cmd[1:]], thumb_path)
    except Exception as exc:
        logger.error(f"ffmpeg thumbnail retry av1_mediacodec failed: {exc}")
        return False


def _attempt(cmd: list[str], thumb_path: Path, video_path: str, is_android: bool) -> bool:
    try:
        return _produced(cmd, thumb_path)
    except subprocess.TimeoutExpired:
        logger.error(f"ffmpeg thumbnail attempt timed out after {FFMPEG_THUMBNAIL_TIMEOUT_SECONDS}s: {video_path}")
    except OSError as err:
        if is_missing_tool_error(err):
            logger.error(f"ffmpeg ne peut pas être lancé ({FFMPEG_BIN}) : {err}")
            raise missing_tool_error("ffmpeg", err) from err
        logger.error(f"ffmpeg thumbnail attempt could not start: {err}")
    except subprocess.CalledProcessError as err:
        stderr = (err.stderr or "").lower()
        if is_android and ("av1" in stderr or "not implemented" in stderr) and _retry_with_av1_decoder(cmd, thumb_path):
            return True
        logger.error(f"ffmpeg thumbnail attempt failed: {err.stderr}")
    return False


def generate_thumbnail(video_path: str, thumbnail_dir: str, duration: float | None) -> str:
    """Génère une miniature à 10% du début de la vidéo à l'aide de ffmpeg."""
    from app.utils.deployment import get_deployment_profile

    thumb_path = Path(thumbnail_dir) / f"thumb_{uuid.uuid4().hex}.jpg"
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    is_android = get_deployment_profile() == "android"
    for offset in _offsets(_initial_offset(duration), duration):
        if _attempt(_command(video_path, offset, thumb_path), thumb_path, video_path, is_android):
            return str(thumb_path)
    time.sleep(1.0)
    if _attempt(_command(video_path, "0.0", thumb_path), thumb_path, video_path, is_android):
        return str(thumb_path)
    raise ValueError("Impossible de générer la miniature avec ffmpeg : le fichier de sortie est vide ou inexistant.")


def generate_placeholder_thumbnail(thumbnail_dir: str, title: str = "") -> str:
    """Miniature de secours (dégradé sobre + initiale) quand ffmpeg ne parvient pas à en extraire une : une carte de fond animé ou de cours audio n'apparaît ainsi jamais « cassée » (vide) dans l'interface."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 640, 360
    image = Image.new("RGB", (width, height), (30, 34, 48))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = int(30 + 40 * y / height)
        draw.line([(0, y), (width, y)], fill=(shade, shade + 4, shade + 22))
    letter = next((c for c in (title or "") if c.isalnum()), "M").upper()
    try:
        font = ImageFont.load_default(size=160)
    except TypeError:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letter, font=font)
    draw.text(((width - (box[2] - box[0])) / 2 - box[0], (height - (box[3] - box[1])) / 2 - box[1]), letter, fill=(205, 210, 235), font=font)
    out = Path(thumbnail_dir) / f"thumb_{uuid.uuid4().hex}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "JPEG", quality=88)
    return str(out)

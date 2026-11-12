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


def generate_thumbnail(video_path: str, thumbnail_dir: str, duration: float | None) -> str:
    """
    Génère une miniature à 10% du début de la vidéo à l'aide de ffmpeg.
    """
    # Calcul de l'offset temporel (10% de la durée, minimum 1.0s, défaut 5.0s)
    offset = 5.0
    if duration:
        offset = max(1.0, duration * 0.1)

    # Si la vidéo est trop courte, on réduit l'offset initial
    if duration and offset >= duration:
        offset = duration * 0.1

    thumb_filename = f"thumb_{uuid.uuid4().hex}.jpg"
    thumb_path = Path(thumbnail_dir) / thumb_filename

    # S'assurer que le dossier de destination existe
    thumb_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        FFMPEG_BIN,
        "-ss", str(offset),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",  # Qualité (1-31, 1 est le meilleur, 2 est quasi sans perte)
        "-strict", "-2",  # Allow unofficial limited-range YUV for mjpeg encoder (needed for FFmpeg 8.0+)
        "-update", "1",   # Prevent single-frame warning/error on output file name
        "-y",
        str(thumb_path)
    ]

    from app.utils.deployment import get_deployment_profile
    is_android = get_deployment_profile() == "android"

    def _try_run_thumb(current_cmd: list[str]) -> bool:
        try:
            subprocess.run(
                with_nostdin(current_cmd), capture_output=True, text=True, check=True,
                timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS, **media_subprocess_kwargs(),
            )
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                return True
        except subprocess.TimeoutExpired:
            # Machine chargée (plusieurs encodages en parallèle sur un Wyse/une tablette) : un dépassement ne
            # doit pas abandonner toute la génération — les essais suivants (début du fichier, plus rapides) restent possibles.
            logger.error(f"ffmpeg thumbnail attempt timed out after {FFMPEG_THUMBNAIL_TIMEOUT_SECONDS}s: {video_path}")
        except OSError as err:
            if is_missing_tool_error(err):
                # Binaire ffmpeg introuvable ou non exécutable : inutile d'insister
                # (les essais suivants échoueraient de la même façon, avec une
                # pause d'une seconde en plus). L'appelant tolère l'échec de
                # miniature (placeholder) ; le message, lui, est explicite.
                logger.error(f"ffmpeg ne peut pas être lancé ({FFMPEG_BIN}) : {err}")
                raise missing_tool_error("ffmpeg", err) from err
            logger.error(f"ffmpeg thumbnail attempt could not start: {err}")
        except subprocess.CalledProcessError as err:
            if is_android and ("av1" in (err.stderr or "").lower() or "not implemented" in (err.stderr or "").lower()):
                # Tentative avec le décodeur matériel MediaCodec
                cmd_retry = [FFMPEG_BIN, "-operating_rate", "1000", "-c:v", "av1_mediacodec"] + current_cmd[1:]
                try:
                    subprocess.run(
                        with_nostdin(cmd_retry), capture_output=True, text=True, check=True,
                        timeout=FFMPEG_THUMBNAIL_TIMEOUT_SECONDS, **media_subprocess_kwargs(),
                    )
                    if thumb_path.exists() and thumb_path.stat().st_size > 0:
                        return True
                except Exception as e_ret:
                    logger.error(f"ffmpeg thumbnail retry av1_mediacodec failed: {e_ret}")
            logger.error(f"ffmpeg thumbnail attempt failed: {err.stderr}")
        return False

    if _try_run_thumb(cmd):
        return str(thumb_path)

    # Premier fallback : offset à 0.1s
    if offset != 0.1:
        new_offset = 0.1
        if duration and new_offset >= duration:
            new_offset = 0.0
        cmd[2] = str(new_offset)
        if _try_run_thumb(cmd):
            return str(thumb_path)

    # Deuxième fallback : début absolu (0.0s)
    cmd[2] = "0.0"
    if _try_run_thumb(cmd):
        return str(thumb_path)

    # Dernier essai : nouvelle tentative au début du fichier après une courte pause (échec transitoire : disque
    # saturé par un import voisin, fichier encore en cours d'écriture...).
    time.sleep(1.0)
    cmd[2] = "0.0"
    if _try_run_thumb(cmd):
        return str(thumb_path)

    raise ValueError("Impossible de générer la miniature avec ffmpeg : le fichier de sortie est vide ou inexistant.")


def generate_placeholder_thumbnail(thumbnail_dir: str, title: str = "") -> str:
    """Miniature de secours (dégradé sobre + initiale) quand ffmpeg ne parvient pas à en extraire une :
    une carte de fond animé ou de cours audio n'apparaît ainsi jamais « cassée » (vide) dans l'interface.
    Pillow uniquement — aucune dépendance à ffmpeg."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 640, 360
    image = Image.new("RGB", (width, height), (30, 34, 48))
    draw = ImageDraw.Draw(image)
    for y in range(height):  # dégradé vertical léger
        shade = int(30 + 40 * y / height)
        draw.line([(0, y), (width, y)], fill=(shade, shade + 4, shade + 22))
    letter = next((c for c in (title or "") if c.isalnum()), "M").upper()
    try:
        font = ImageFont.load_default(size=160)
    except TypeError:  # Pillow ancien : police bitmap par défaut, plus petite
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), letter, font=font)
    draw.text(((width - (box[2] - box[0])) / 2 - box[0], (height - (box[3] - box[1])) / 2 - box[1]), letter, fill=(205, 210, 235), font=font)
    out = Path(thumbnail_dir) / f"thumb_{uuid.uuid4().hex}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, "JPEG", quality=88)
    return str(out)

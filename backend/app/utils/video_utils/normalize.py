"""Normalisation d'une vidéo importée."""
import os
import logging
from pathlib import Path
from app.utils.ffmpeg_binaries import (
    FFMPEG_BIN,
)
from app.videos.encoding import get_encoder_args, get_transcode_pipeline
from app.utils.video_utils.probe import extract_metadata
from app.utils.video_utils.progress import run_ffmpeg_with_progress


logger = logging.getLogger(__name__)


def estimate_normalize_seconds(source_metadata: dict) -> float | None:
    """Estimation de la durée de réencodage AVANT le démarrage de ffmpeg."""
    from app.utils.deployment import get_deployment_profile
    from app.utils.encode_speed_stats import get_estimated_speed, resolution_bucket

    duration = source_metadata.get("duration_seconds")
    if not duration or duration <= 0:
        return None
    is_android = get_deployment_profile() == "android"
    _, encoder_name = get_encoder_args(is_android, source_metadata.get("width"), source_metadata.get("height"))
    speed = get_estimated_speed(encoder_name, resolution_bucket(source_metadata.get("width"), source_metadata.get("height")))
    if speed <= 0:
        return None
    return duration / speed


_STREAM_COPY = {"name": "stream_copy", "encoder_name": None, "hw_in": [], "enc_args": ["-c:v", "copy"]}


def _audio_args(meta: dict, actions: list[str]) -> list[str]:
    audio_codec = meta.get("audio_codec")
    if audio_codec is None:
        return ["-an"]
    if "recode_audio" in actions and audio_codec.lower() != "aac":
        return ["-c:a", "aac"]
    return ["-c:a", "copy"]


def _normalize_command(input_path: str, output_path: str, actions: list[str], meta: dict, tier: dict) -> list[str]:
    video = tier["enc_args"] if "recode_video" in actions else ["-c:v", "copy"]
    return [
        FFMPEG_BIN, *tier["hw_in"], "-threads", "0", "-i", input_path, *video, *_audio_args(meta, actions),
        "-threads", "0", "-movflags", "+faststart", "-y", output_path,
    ]


def _last_lines(stderr: str, count: int = 3) -> str:
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    return " ; ".join(lines[-count:]) or "erreur inconnue"


def _has_video(path: str) -> bool:
    try:
        meta = extract_metadata(path)
    except Exception as exc:
        logger.warning(f"Sortie de normalisation illisible ({path}) : {exc}")
        return False
    return bool(meta.get("codec")) and (meta.get("duration_seconds") or 0) > 0


def _discard(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def normalize_video(
    input_path: str,
    output_path: str,
    actions: list[str],
    source_metadata: dict | None = None,
    job_id: str | None = None,
) -> str:
    """Normalise le conteneur ou la piste audio/vidéo d'une vidéo de manière optimisée."""
    from app.utils.deployment import get_deployment_profile
    from app.utils.import_jobs import is_job_cancelled, JobCancelledError

    if is_job_cancelled(job_id):
        raise JobCancelledError(f"Job {job_id} annulé")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    meta = source_metadata if source_metadata is not None else extract_metadata(input_path)
    if "recode_video" in actions:
        is_android = get_deployment_profile() == "android"
        tiers = get_transcode_pipeline(is_android, (meta.get("codec") or "").lower(), meta.get("width"), meta.get("height"))
    else:
        tiers = [_STREAM_COPY]
    last_error_stderr = ""
    for idx, tier in enumerate(tiers):
        logger.info(f"Tentative de normalisation vidéo (palier {idx + 1}/{len(tiers)}: {tier['name']})...")
        ret, stderr = run_ffmpeg_with_progress(
            _normalize_command(input_path, output_path, actions, meta, tier), job_id, meta.get("duration_seconds"),
            encoder_name=tier["encoder_name"], width=meta.get("width"), height=meta.get("height"),
        )
        if ret == 0 and _has_video(output_path):
            return output_path
        if ret == 0:
            stderr = "sortie sans piste vidéo lisible"
        last_error_stderr = stderr
        logger.warning(f"Échec de l'encodage avec {tier['name']} ({tier['encoder_name']}) (code {ret}): {stderr}")
        _discard(output_path)
    raise ValueError(f"Échec de la normalisation de la vidéo avec ffmpeg : {_last_lines(last_error_stderr)}")

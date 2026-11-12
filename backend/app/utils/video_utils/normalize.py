"""Normalisation d'une vidéo importée."""
import os
import logging
from pathlib import Path
from app.utils.ffmpeg_binaries import (
    FFMPEG_BIN,
)
from app.utils.video_utils.encoders import get_encoder_args, get_transcode_pipeline
from app.utils.video_utils.probe import extract_metadata
from app.utils.video_utils.progress import run_ffmpeg_with_progress


logger = logging.getLogger(__name__)


def estimate_normalize_seconds(source_metadata: dict) -> float | None:
    """Estimation de la durée de réencodage AVANT le démarrage de ffmpeg : basée sur la vitesse moyenne (x temps réel) déjà observée pour ce couple (encodeur, résolution) via `encode_speed_stats`, ou un repère par défaut tant qu'aucun échantillon n'existe encore."""
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
    in_codec = (meta.get("codec") or "").lower()
    is_android = get_deployment_profile() == "android"

    def _build_cmd(hw_in: list[str], enc_args: list[str]) -> list[str]:
        c = [FFMPEG_BIN]
        if hw_in:
            c.extend(hw_in)
        c.extend(["-threads", "0", "-i", input_path])
        if "recode_video" in actions:
            c.extend(enc_args)
        else:
            c.extend(["-c:v", "copy"])

        has_audio = meta.get("audio_codec") is not None
        if not has_audio:
            c.append("-an")
        elif "recode_audio" in actions and (meta.get("audio_codec") or "").lower() != "aac":
            c.extend(["-c:a", "aac"])
        else:
            c.extend(["-c:a", "copy"])

        c.extend(["-threads", "0", "-movflags", "+faststart", "-y", output_path])
        return c

    if "recode_video" in actions:
        tiers = get_transcode_pipeline(is_android, in_codec, meta.get("width"), meta.get("height"))
    else:
        tiers = [{"name": "stream_copy", "encoder_name": None, "hw_in": [], "enc_args": ["-c:v", "copy"]}]

    last_error_stderr = ""
    for idx, tier in enumerate(tiers):
        cmd = _build_cmd(tier["hw_in"], tier["enc_args"])
        logger.info(f"Tentative de normalisation vidéo (palier {idx + 1}/{len(tiers)}: {tier['name']})...")
        ret, stderr = run_ffmpeg_with_progress(
            cmd,
            job_id,
            meta.get("duration_seconds"),
            encoder_name=tier["encoder_name"],
            width=meta.get("width"),
            height=meta.get("height"),
        )
        if ret == 0:
            return output_path

        last_error_stderr = stderr
        logger.warning(f"Échec de l'encodage avec {tier['name']} ({tier['encoder_name']}) (code {ret}): {stderr}")

        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass

    raise ValueError(f"Échec de la normalisation de la vidéo avec ffmpeg : {last_error_stderr}")

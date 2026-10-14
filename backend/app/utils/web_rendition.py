"""Production de la version web « lisible partout » d'une vidéo (lot F3 du
plan de compatibilité Firefox). Logique pure : `app/utils/web_profile.py` ;
ici, la tâche d'arrière-plan (ffmpeg, suivi dans `import_jobs`, état en base).

Les fichiers vivent dans `<media_dir>/web/` — sous-dossier volontaire :
`importer.reconcile_orphaned_media` n'examine que les fichiers à la racine du
dossier média et signalerait sinon chaque version web comme « orpheline »."""

import logging
import os
import threading
import uuid
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import Video
from app.utils.executors import ffmpeg_executor
from app.utils.ffmpeg_binaries import FFMPEG_BIN
from app.utils.import_jobs import JobCancelledError, create_job, register_job_future, update_job
from app.utils.web_profile import build_web_rendition_command
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

# Une version web à la fois par vidéo : un double clic ou deux clients
# simultanés (négociation automatique) ne doivent jamais lancer deux ffmpeg
# sur la même source.
_inflight_lock = threading.Lock()
_inflight: set[int] = set()


def web_dir() -> Path:
    path = Path(settings.media_dir) / "web"
    path.mkdir(parents=True, exist_ok=True)
    return path


def remove_web_file(web_path: str | None) -> None:
    if not web_path:
        return
    try:
        Path(web_path).unlink(missing_ok=True)
    except OSError as e:
        logger.error(f"Impossible de supprimer la version web {web_path} : {e}")


def request_web_rendition(video_id: int) -> str | None:
    """Met en file la production de la version web ; renvoie l'identifiant de
    tâche, ou None si une production est déjà en cours pour cette vidéo."""
    with _inflight_lock:
        if video_id in _inflight:
            return None
        _inflight.add(video_id)

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            with _inflight_lock:
                _inflight.discard(video_id)
            return None
        video.web_status = "pending"
        db.commit()
        title = video.title
    finally:
        db.close()

    job_id = create_job("web_rendition", title, title)
    future = ffmpeg_executor.submit(_run_job, job_id, video_id)
    register_job_future(job_id, future)
    return job_id


def _run_job(job_id: str, video_id: int) -> None:
    from app.utils.video_utils import FFMPEG_NORMALIZE_TIMEOUT_SECONDS, _run_ffmpeg_with_progress

    output = None
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video or not video.file_path or not Path(video.file_path).exists():
            raise FileNotFoundError("Fichier source introuvable")
        update_job(job_id, stage="normalizing")
        output = str(web_dir() / f"web_{video_id}_{uuid.uuid4().hex[:8]}.part.mp4")
        command = build_web_rendition_command(
            FFMPEG_BIN, video.file_path, output, video.height, video.fps, has_audio=video.audio_codec is not None,
        )
        ret, stderr = _run_ffmpeg_with_progress(
            command, job_id, video.duration_seconds, timeout=FFMPEG_NORMALIZE_TIMEOUT_SECONDS * 2,
            width=video.width, height=video.height,
        )
        if ret != 0:
            raise RuntimeError(f"ffmpeg a échoué (code {ret}) : {stderr[-400:]}")
        final = output.replace(".part.mp4", ".mp4")
        os.replace(output, final)
        output = None
        old = video.web_path
        video.web_path, video.web_status = final, "ready"
        db.commit()
        if old and old != final:
            remove_web_file(old)
        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "web_rendition_ready"})
        update_job(job_id, stage="done", result_id=video_id)
    except JobCancelledError:
        _mark(db, video_id, None)
        update_job(job_id, stage="cancelled")
    except Exception as e:
        logger.error(f"Échec de la version web de la vidéo {video_id} : {e}", exc_info=True)
        _mark(db, video_id, "error")
        update_job(job_id, stage="error", error=str(e))
    finally:
        if output:
            remove_web_file(output)
        db.close()
        with _inflight_lock:
            _inflight.discard(video_id)


def _mark(db, video_id: int, status: str | None) -> None:
    try:
        db.rollback()
        video = db.query(Video).filter(Video.id == video_id).first()
        if video and video.web_status != "ready":
            video.web_status = status
            db.commit()
    except Exception as e:
        logger.error(f"Impossible de mettre à jour l'état de la version web ({video_id}) : {e}")

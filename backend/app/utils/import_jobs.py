import concurrent.futures
import os
import subprocess
import threading
import time
import uuid
import logging

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_job_order: list[str] = []
_job_futures: dict[str, concurrent.futures.Future] = {}
_job_leftovers: dict[str, list[str]] = {}
_job_processes: dict[str, subprocess.Popen] = {}
_cancelled_jobs: set[str] = set()


class JobCancelledError(Exception):
    """Levée lorsqu'une tâche d'importation a été annulée par l'utilisateur."""
    pass


ACTIVE_TTL_SECONDS = 3600
DONE_TTL_SECONDS = 300

_STAGE_LABELS = {
    "queued": "En attente",
    "probing": "Analyse du fichier",
    "normalizing": "Réencodage",
    "copying": "Déplacement du fichier",
    "thumbnail": "Génération de la miniature",
    "extracting": "Extraction de l'archive",
    "saving": "Enregistrement",
    "done": "Terminé",
    "error": "Échec",
    "cancelled": "Annulé",
}


def _ttl_for(job: dict) -> int:
    return DONE_TTL_SECONDS if job.get("stage") in ("done", "error", "cancelled") else ACTIVE_TTL_SECONDS


def _is_expired(job: dict) -> bool:
    return time.time() - job["updated_at"] > _ttl_for(job)


def create_job(kind: str, filename: str, title: str | None = None, source: str = "upload") -> str:
    """Enregistre une nouvelle tâche d'import (stage initial "queued") et retourne son identifiant."""
    job_id = uuid.uuid4().hex
    now = time.time()
    job = {
        "id": job_id,
        "kind": kind,
        "source": source,
        "filename": filename,
        "title": title,
        "stage": "queued",
        "stage_label": _STAGE_LABELS["queued"],
        "error": None,
        "error_code": None,
        "error_params": None,
        "result_id": None,
        "progress_percent": None,
        "eta_seconds": None,
        "speed": None,
        "estimated_seconds": None,
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        _jobs[job_id] = job
        _job_order.append(job_id)
    return job_id


def register_job_future(job_id: str, future: concurrent.futures.Future, leftovers: list[str] | None = None) -> None:
    """Associe la Future d'un exécuteur à une tâche pour permettre son annulation en file."""
    with _lock:
        _job_futures[job_id] = future
        if leftovers:
            _job_leftovers[job_id] = list(leftovers)


def register_job_process(job_id: str | None, proc: subprocess.Popen) -> None:
    """Associe le processus sous-jacent."""
    if not job_id:
        return
    with _lock:
        _job_processes[job_id] = proc


def unregister_job_process(job_id: str | None) -> None:
    """Désenregistre le processus une fois son exécution terminée."""
    if not job_id:
        return
    with _lock:
        _job_processes.pop(job_id, None)


def is_job_cancelled(job_id: str | None) -> bool:
    """Vérifie si la tâche a été marquée comme annulée."""
    if not job_id:
        return False
    with _lock:
        return job_id in _cancelled_jobs or (_jobs.get(job_id, {}).get("stage") == "cancelled")


def cancel_job(job_id: str) -> bool:
    """Annule immédiatement une tâche d'importation en cours ou en attente : 1."""
    future = None
    proc = None
    found = False

    with _lock:
        _cancelled_jobs.add(job_id)
        job = _jobs.get(job_id)
        if job is not None:
            found = True
            job["stage"] = "cancelled"
            job["stage_label"] = _STAGE_LABELS["cancelled"]
            job["updated_at"] = time.time()
        future = _job_futures.pop(job_id, None)
        proc = _job_processes.pop(job_id, None)
        leftovers = _job_leftovers.pop(job_id, [])

    if future is not None and not future.done():
        if future.cancel():
            logger.info(f"Future de l'import {job_id} annulée dans la file d'attente.")
            for path in leftovers:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    if proc is not None:
        try:
            logger.info(f"Arrêt forcé du processus FFmpeg pour l'import {job_id} (PID {proc.pid})...")
            proc.terminate()
            try:
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1.0)
            logger.info(f"Processus FFmpeg pour l'import {job_id} arrêté.")
        except Exception as e:
            logger.warning(f"Erreur lors de l'arrêt du processus pour l'import {job_id}: {e}")

    return found


def update_job(job_id: str | None, **fields) -> None:
    """Met à jour les champs fournis d'une tâche existante."""
    if not job_id:
        return
    with _lock:
        job = _jobs.get(job_id)
        if job is None or _is_expired(job):
            return
        job.update(fields)
        if fields.get("stage") == "error" and fields.get("error"):
            from app.utils.ffmpeg_binaries import classify_error

            classified = classify_error(str(fields["error"]))
            if classified:
                job["error_code"], job["error_params"] = classified
        if "stage" in fields:
            job["stage_label"] = _STAGE_LABELS.get(fields["stage"], fields["stage"])
        job["updated_at"] = time.time()


def get_job(job_id: str) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None or _is_expired(job):
            return None
        return dict(job)


def list_jobs() -> list[dict]:
    """Tâches d'import récentes (en cours, ou terminées depuis moins de DONE_TTL_SECONDS), triées par ordre de création."""
    with _lock:
        stale_ids = [job_id for job_id in _job_order if job_id not in _jobs or _is_expired(_jobs[job_id])]
        for job_id in stale_ids:
            _job_order.remove(job_id)
            _jobs.pop(job_id, None)
            _job_futures.pop(job_id, None)
            _job_leftovers.pop(job_id, None)
            _job_processes.pop(job_id, None)
            _cancelled_jobs.discard(job_id)
        jobs = [dict(_jobs[job_id]) for job_id in _job_order]

    pending = [j for j in jobs if j["stage"] not in ("done", "error", "cancelled")]
    cumulative = 0.0
    for idx, job in enumerate(pending):
        job["queue_position"] = idx
        own_remaining = job.get("eta_seconds")
        if own_remaining is None:
            own_remaining = job.get("estimated_seconds") or 0.0
        cumulative += own_remaining
        job["queue_eta_seconds"] = round(cumulative)

    return jobs

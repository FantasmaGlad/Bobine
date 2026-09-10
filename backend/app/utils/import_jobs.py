import concurrent.futures
import subprocess
import threading
import time
import uuid
import logging

logger = logging.getLogger(__name__)

# Suivi de file d'import (réf. mission "voir en direct les importations et
# l'estimation d'où elles en sont") : les imports (upload web ET dossier
# surveillé) tournent sur des exécuteurs à threads (app.utils.executors),
# appelés depuis les threads des exécuteurs ET consultés depuis les threads
# de requêtes HTTP (asyncio + threads combinés) — un simple dict protégé par
# un verrou suffit pour un état partagé entre threads d'un même processus
# (réf. PortabiliteCrossPlatformX, Lot 0 — avant la suppression de Redis,
# cet état devait être visible de tous les workers uvicorn ; process unique
# depuis ce lot, l'état en mémoire de CE processus est déjà visible de
# toutes les requêtes).
_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_job_order: list[str] = []  # ids dans l'ordre de création (remplace le zset Redis)
_job_futures: dict[str, concurrent.futures.Future] = {}
_job_processes: dict[str, subprocess.Popen] = {}
_cancelled_jobs: set[str] = set()


class JobCancelledError(Exception):
    """Levée lorsqu'une tâche d'importation a été annulée par l'utilisateur."""
    pass


# Le réencodage le plus long observé en production a dépassé 15 min (cf.
# FFMPEG_NORMALIZE_TIMEOUT_SECONDS = 1800 dans video_utils.py) : la tâche doit
# rester visible largement au-delà, sans quoi elle "disparaîtrait" de la
# file en cours de traitement.
ACTIVE_TTL_SECONDS = 3600
# Une tâche terminée (succès, erreur ou annulation) reste visible quelques minutes pour
# que l'utilisateur voie le résultat, puis s'efface d'elle-même — pas besoin
# de nettoyage explicite.
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
    """Enregistre une nouvelle tâche d'import (stage initial "queued") et
    retourne son identifiant. Appelé AVANT de soumettre le travail réel à
    l'exécuteur, pour que la tâche apparaisse dans la file dès son
    acceptation plutôt qu'à son démarrage effectif."""
    job_id = uuid.uuid4().hex
    now = time.time()
    job = {
        "id": job_id,
        "kind": kind,  # "video" | "background" | "audio"
        "source": source,  # "upload" | "watched_folder"
        "filename": filename,
        "title": title,
        "stage": "queued",
        "stage_label": _STAGE_LABELS["queued"],
        "error": None,
        "result_id": None,
        "progress_percent": None,
        "eta_seconds": None,
        "speed": None,
        # Estimation initiale du réencodage, posée avant même le démarrage de
        # ffmpeg (réf. mission "estimation de la durée d'importation et de
        # réencodage", cf. video_utils.estimate_normalize_seconds) — écrasée
        # par `eta_seconds` dès que la progression ffmpeg réelle démarre.
        "estimated_seconds": None,
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        _jobs[job_id] = job
        _job_order.append(job_id)
    return job_id


def register_job_future(job_id: str, future: concurrent.futures.Future) -> None:
    """Associe la Future d'un exécuteur à une tâche pour permettre son annulation en file."""
    with _lock:
        _job_futures[job_id] = future


def register_job_process(job_id: str | None, proc: subprocess.Popen) -> None:
    """Associe le processus sous-jacent (ex. FFmpeg) à la tâche en cours pour permettre
    son arrêt forcé immédiat en cas d'annulation."""
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
    """
    Annule immédiatement une tâche d'importation en cours ou en attente :
    1. Marque le job avec stage="cancelled".
    2. Annule la Future dans l'exécuteur si elle n'a pas encore démarré.
    3. Interrompt le processus FFmpeg (SIGTERM puis SIGKILL) s'il tourne.
    """
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

    if future is not None and not future.done():
        future.cancel()
        logger.info(f"Future de l'import {job_id} annulée dans la file d'attente.")

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
    """Met à jour les champs fournis d'une tâche existante (no-op silencieux
    si `job_id` est None — permet aux fonctions d'import de rester utilisables
    sans job à suivre, ex. import déclenché depuis les tests)."""
    if not job_id:
        return
    with _lock:
        job = _jobs.get(job_id)
        if job is None or _is_expired(job):
            return
        job.update(fields)
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
    """Tâches d'import récentes (en cours, ou terminées depuis moins de
    DONE_TTL_SECONDS), triées par ordre de création. Calcule aussi une
    `queue_position` (réf. mission "estimation d'où elles en sont") : nombre
    de tâches non terminées créées avant celle-ci — une ESTIMATION, pas la
    position exacte dans l'exécuteur ffmpeg mono-thread partagé
    (app.utils.executors.ffmpeg_executor) qui arbitre le vrai tour de rôle."""
    with _lock:
        stale_ids = [job_id for job_id in _job_order if job_id not in _jobs or _is_expired(_jobs[job_id])]
        for job_id in stale_ids:
            _job_order.remove(job_id)
            _jobs.pop(job_id, None)
            _job_futures.pop(job_id, None)
            _job_processes.pop(job_id, None)
            _cancelled_jobs.discard(job_id)
        jobs = [dict(_jobs[job_id]) for job_id in _job_order]

    pending = [j for j in jobs if j["stage"] not in ("done", "error", "cancelled")]
    # ETA de file cumulée (réf. mission "estimation de la durée d'importation
    # et de réencodage") : pour chaque tâche non terminée, temps encore
    # nécessaire pour ELLE-MÊME (l'ETA ffmpeg en direct si l'encodage est déjà
    # démarré, sinon l'estimation initiale posée en fin d'analyse, sinon 0
    # pour les étapes rapides sans estimation dédiée — copie, miniature,
    # enregistrement), additionné à celui de toutes les tâches placées avant
    # elle dans la file. Une ESTIMATION au même titre que `queue_position`
    # ci-dessus, pas une garantie.
    cumulative = 0.0
    for idx, job in enumerate(pending):
        job["queue_position"] = idx
        own_remaining = job.get("eta_seconds")
        if own_remaining is None:
            own_remaining = job.get("estimated_seconds") or 0.0
        cumulative += own_remaining
        job["queue_eta_seconds"] = round(cumulative)

    return jobs

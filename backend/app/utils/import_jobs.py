import threading
import time
import uuid

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

# Le réencodage le plus long observé en production a dépassé 15 min (cf.
# FFMPEG_NORMALIZE_TIMEOUT_SECONDS = 1800 dans video_utils.py) : la tâche doit
# rester visible largement au-delà, sans quoi elle "disparaîtrait" de la
# file en cours de traitement.
ACTIVE_TTL_SECONDS = 3600
# Une tâche terminée (succès ou erreur) reste visible quelques minutes pour
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
}


def _ttl_for(job: dict) -> int:
    return DONE_TTL_SECONDS if job.get("stage") in ("done", "error") else ACTIVE_TTL_SECONDS


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
        "created_at": now,
        "updated_at": now,
    }
    with _lock:
        _jobs[job_id] = job
        _job_order.append(job_id)
    return job_id


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
        jobs = [dict(_jobs[job_id]) for job_id in _job_order]

    pending = [j for j in jobs if j["stage"] not in ("done", "error")]
    for idx, job in enumerate(pending):
        job["queue_position"] = idx

    return jobs

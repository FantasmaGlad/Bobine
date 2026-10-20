"""Diagnostic de la chaîne d'import (`GET /api/diagnostics/import`).

Pourquoi : un import qui reste à 0 % sans erreur (signalé en production sur
macOS) laissait l'utilisateur et le support sans aucun moyen de savoir si
ffmpeg était absent, si le dossier temporaire était inaccessible ou plein, ou
si un import précédent occupait l'unique thread ffmpeg. Ce point d'entrée
regroupe ces constats en une seule réponse lisible depuis Réglages.

Règle de robustesse (jamais de HTTP 500 sur un appel d'état) : chaque bloc est
calculé dans son propre `try/except` ; un échec devient `{"error": "..."}` pour
ce bloc seulement, le reste de la réponse reste exploitable.
"""

import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter

from app.utils import ffmpeg_binaries

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

# En dessous, un import de quelques Go (vidéo + copie normalisée) échoue pour
# manque de place avant même de démarrer.
LOW_DISK_BYTES = 2 * 1024**3
# Une tâche active sans aucune mise à jour (progression, étape) depuis ce délai
# est suspecte : même un réencodage long met sa progression à jour chaque seconde.
STUCK_JOB_SECONDS = 300


def _safe(block: Callable[[], Any]) -> Any:
    try:
        return block()
    except Exception as exc:  # noqa: BLE001 — règle d'or : jamais d'exception vers l'API
        logger.warning("Diagnostic d'import : bloc en échec : %s: %s", type(exc).__name__, exc)
        return {"error": f"{type(exc).__name__}: {exc}"}


def _directory_state(path: Path | str) -> dict:
    """Existence, accès en écriture (par création réelle d'un fichier : les bits
    de permission ne disent pas tout, ex. volume en lecture seule) et espace libre."""
    target = Path(path)
    state: dict = {"path": str(target), "exists": target.is_dir(), "writable": False, "free_bytes": None, "total_bytes": None}
    if not state["exists"]:
        return state
    try:
        import shutil

        usage = shutil.disk_usage(target)
        state["free_bytes"], state["total_bytes"] = usage.free, usage.total
    except OSError as exc:
        state["error"] = f"espace disque illisible : {exc}"
    try:
        with tempfile.NamedTemporaryFile(dir=target, prefix=".bobine-diag-"):
            state["writable"] = True
    except OSError as exc:
        state["error"] = f"écriture impossible : {exc}"
    return state


def _executor_state() -> dict:
    from app.utils.executors import ffmpeg_executor, io_executor

    def describe(executor) -> dict:
        threads = getattr(executor, "_threads", None) or set()
        queue = getattr(executor, "_work_queue", None)
        return {
            "max_workers": getattr(executor, "_max_workers", None),
            "threads_started": len(threads),
            "threads_alive": sum(1 for t in threads if t.is_alive()),
            "queued": queue.qsize() if queue is not None else None,
            "shutdown": bool(getattr(executor, "_shutdown", False)),
        }

    return {"ffmpeg": describe(ffmpeg_executor), "io": describe(io_executor)}


def _jobs_state() -> dict:
    from app.utils.import_jobs import list_jobs

    now = time.time()
    finished = ("done", "error", "cancelled")
    active = []
    counts: dict[str, int] = {}
    for job in list_jobs():
        counts[job["stage"]] = counts.get(job["stage"], 0) + 1
        if job["stage"] in finished:
            continue
        active.append({
            "id": job["id"][:8],
            "kind": job.get("kind"),
            "source": job.get("source"),
            "stage": job["stage"],
            "age_seconds": round(now - job["created_at"], 1),
            "idle_seconds": round(now - job["updated_at"], 1),
            "queue_position": job.get("queue_position"),
        })
    return {"active": active, "counts": counts}


def _staging_state() -> dict:
    from app.utils import staged_uploads

    base = _directory_state(staged_uploads.staging_dir())
    parts = list(Path(base["path"]).glob("*.part"))
    base["partial_uploads"] = len(parts)
    base["partial_bytes"] = sum(p.stat().st_size for p in parts if p.exists())
    return base


def _problems(report: dict) -> list[str]:
    """Constats à afficher en tête de Réglages (codes stables, traduits côté client)."""
    problems: list[str] = []
    for tool in ("ffmpeg", "ffprobe"):
        info = report.get(tool)
        if isinstance(info, dict) and not (info.get("found") and info.get("executable") and not info.get("error")):
            problems.append(f"{tool}_unavailable")
    temp = report.get("temp_dir")
    if isinstance(temp, dict) and temp.get("exists") is not None:
        if not temp.get("exists") or not temp.get("writable"):
            problems.append("temp_not_writable")
        free = temp.get("free_bytes")
        if isinstance(free, int) and free < LOW_DISK_BYTES:
            problems.append("disk_low")
    jobs = report.get("jobs")
    if isinstance(jobs, dict):
        if any(j.get("idle_seconds", 0) > STUCK_JOB_SECONDS for j in jobs.get("active", [])):
            problems.append("job_stuck")
    executors = report.get("executors")
    if isinstance(executors, dict) and isinstance(executors.get("ffmpeg"), dict):
        if executors["ffmpeg"].get("shutdown"):
            problems.append("executor_shutdown")
    return problems


@router.get("/import")
def import_diagnostics() -> dict:
    """État de la chaîne d'import : binaires, dossiers, exécuteur et tâches."""
    from app.config import settings

    report: dict = {
        "generated_at": time.time(),
        "os": _safe(ffmpeg_binaries.os_key),
        "frozen": bool(getattr(sys, "frozen", False)),
        "ffmpeg": _safe(lambda: ffmpeg_binaries.probe_tool(ffmpeg_binaries.FFMPEG_BIN)),
        "ffprobe": _safe(lambda: ffmpeg_binaries.probe_tool(ffmpeg_binaries.FFPROBE_BIN)),
        "temp_dir": _safe(lambda: _directory_state(tempfile.gettempdir())),
        "staging_dir": _safe(_staging_state),
        "media_dir": _safe(lambda: _directory_state(settings.media_dir)),
        "executors": _safe(_executor_state),
        "jobs": _safe(_jobs_state),
    }
    report["problems"] = _safe(lambda: _problems(report))
    if isinstance(report["problems"], dict):  # le calcul des constats a lui-même échoué
        report["problems"] = []
    return report

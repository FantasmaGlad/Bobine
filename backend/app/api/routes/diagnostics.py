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
            "job_id": job["id"],  # identifiant complet : `bobine diagnose --auto-fix` annule par lui
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


# ---------------------------------------------------------------------------
# Diagnostic système (`GET /api/diagnostics/system`) : un constat typé par problème, pour l'interface, la CLI et un
# agent externe. Sondes rapides et locales seulement (aucun appel réseau, aucun droit administrateur) : la santé
# SMART des supports et le test Tor restent des actions explicites de leurs propres pages.
# ---------------------------------------------------------------------------

SEVERITIES = ("critical", "warning", "info")
# Sous ce seuil, le prochain import ou réencodage d'une vidéo longue risque de manquer de place.
LOW_MEDIA_DISK_BYTES = 5 * 1024**3


class _Report:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.problems: list[dict[str, str]] = []

    def check(self, name: str, status: str, detail: str | None = None) -> None:
        entry: dict[str, Any] = {"name": name, "status": status}
        if detail:
            entry["detail"] = detail
        self.checks.append(entry)

    def problem(self, check: str, code: str, severity: str, message: str, remedy: str, fix: dict | None = None) -> None:
        """`fix` (facultatif) décrit une correction sans risque que `bobine diagnose --auto-fix` peut appliquer :
        `{"action": "cancel_import_jobs", "job_ids": [...]}` ou `{"action": "set_settings", "settings": {...}}`."""
        entry = {"code": code, "severity": severity, "message": message, "remedy": remedy}
        if fix:
            entry["fix"] = fix
        self.problems.append(entry)
        if not any(c["name"] == check for c in self.checks):
            self.check(check, "problem")

    def probe(self, name: str, function: Callable[["_Report"], None]) -> None:
        """Une sonde qui échoue devient `unknown` avec sa raison : jamais d'erreur 500 sur un appel d'état."""
        before = len(self.problems)
        try:
            function(self)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Diagnostic système : sonde %s en échec : %s", name, exc)
            del self.problems[before:]
            self.checks = [c for c in self.checks if c["name"] != name]
            self.check(name, "unknown", f"{type(exc).__name__}: {exc}")
            return
        if not any(c["name"] == name for c in self.checks):
            self.check(name, "ok")


def _probe_database(report: _Report) -> None:
    from sqlalchemy import text

    from app.database import SessionLocal

    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        report.problem("database", "database_unreachable", "critical", f"La base de données ne répond pas ({exc}).",
                       "Vérifier le fichier de la base, ses droits et l'espace disque, puis redémarrer Bobine.")


def _probe_kiosk(report: _Report) -> None:
    from app.utils.deployment import get_profile_handler
    from app.utils.health import kiosk_process_alive

    if get_profile_handler().profile != "linux-headless":
        report.check("kiosk", "not_applicable", "pas de kiosque séparé à superviser sur ce profil")
        return
    state = kiosk_process_alive()
    if state == "down":
        report.problem("kiosk", "kiosk_down", "warning", "Le navigateur du kiosque ne tourne pas sur l'appliance.",
                       "Redémarrer le service du kiosque (le chien de garde le relance normalement seul).")
    elif state == "unknown":
        report.check("kiosk", "unknown", "liste des processus illisible")


def _probe_port(report: _Report) -> None:
    from app.utils.port import active_port, preferred_port, read_runtime

    runtime = read_runtime(require_live=False) or {}
    port, wanted = active_port(), int(runtime.get("preferred") or preferred_port())
    if port != wanted:
        report.problem("port", "port_fallback", "warning",
                       f"Bobine écoute sur le port {port} : le port {wanted} n'était pas disponible au démarrage.",
                       f"Libérer le port {wanted} ou en choisir un autre (BOBINE_PORT), puis redémarrer Bobine ; "
                       "les adresses à jour sont dans Réglages → Documentation.")


def _probe_network(report: _Report) -> None:
    from app.utils.mdns import get_status as mdns_status
    from app.utils.network import lan_addresses

    if not lan_addresses():
        report.problem("network", "no_lan_address", "warning", "Aucune adresse sur le réseau local.",
                       "Vérifier le câble, le Wi-Fi ou le DHCP ; seul l'accès local (127.0.0.1) fonctionne.")
    state = mdns_status().get("state")
    if state in ("failed", "unavailable"):
        report.problem("network", f"mdns_{state}", "warning", "Le nom bobine.local n'est pas publié sur le réseau.",
                       "Utiliser l'adresse IP de Réglages → Documentation ; vérifier le pare-feu (port 5353 UDP).")


def _probe_firewall(report: _Report) -> None:
    from app.utils import firewall

    state = firewall.status()
    if state["state"] == "blocked":
        report.problem("firewall", "firewall_blocks_bobine", "warning",
                       "Le pare-feu de macOS bloque les connexions entrantes vers Bobine : seul ce poste y accède.",
                       f"Dans un Terminal : {state['remedy']}")
    elif state["state"] == "rule_missing":
        report.problem("firewall", "firewall_rule_missing", "warning",
                       "La règle de pare-feu Windows « Bobine » est absente : les autres appareils du réseau ne joignent pas Bobine.",
                       state["remedy"])
    elif state["state"] == "not_checked":
        report.check("firewall", "ok", state.get("reason"))


def _probe_media_tools(report: _Report) -> None:
    for tool, binary in (("ffmpeg", ffmpeg_binaries.FFMPEG_BIN), ("ffprobe", ffmpeg_binaries.FFPROBE_BIN)):
        info = ffmpeg_binaries.probe_tool(binary)
        if not (info.get("found") and info.get("executable") and not info.get("error")):
            report.problem("media_tools", f"{tool}_unavailable", "critical", f"{tool} est introuvable ou inutilisable.",
                           f"Réinstaller Bobine (il embarque {tool}) ou installer {tool} sur le système.")


def _probe_disks(report: _Report) -> None:
    from app.config import settings

    temp = _directory_state(tempfile.gettempdir())
    if not temp["exists"] or not temp["writable"]:
        report.problem("disk", "temp_not_writable", "critical", "Le dossier temporaire des imports n'est pas inscriptible.",
                       "Corriger les droits du dossier temporaire ou libérer de la place.")
    elif isinstance(temp["free_bytes"], int) and temp["free_bytes"] < LOW_DISK_BYTES:
        report.problem("disk", "disk_low", "critical", "Moins de 2 Go libres pour les imports.",
                       "Supprimer des médias inutilisés ou déplacer les données vers un disque plus grand.")
    media = _directory_state(settings.media_dir)
    if isinstance(media["free_bytes"], int) and media["free_bytes"] < LOW_MEDIA_DISK_BYTES:
        report.problem("disk", "disk_low_media", "warning", "Moins de 5 Go libres sur le disque des médias.",
                       "Supprimer des médias inutilisés ou ajouter un support externe.")


def _probe_imports(report: _Report) -> None:
    jobs = _jobs_state()
    stuck = [j for j in jobs["active"] if j["idle_seconds"] > STUCK_JOB_SECONDS]
    if stuck:
        report.problem("imports", "import_job_stuck", "warning", f"{len(stuck)} import(s) sans progression depuis plus de 5 minutes.",
                       "Annuler l'import concerné puis consulter le journal technique.",
                       fix={"action": "cancel_import_jobs", "job_ids": [j["job_id"] for j in stuck]})
    if _executor_state()["ffmpeg"]["shutdown"]:
        report.problem("imports", "import_executor_shutdown", "critical", "Le moteur de traitement des médias est arrêté.",
                       "Redémarrer Bobine.")
    staging = _staging_state()
    if staging.get("partial_uploads"):
        report.problem("imports", "staged_uploads_pending", "info",
                       f"{staging['partial_uploads']} transfert(s) inachevé(s) en attente de reprise.",
                       "Reprendre le transfert depuis la page d'import, ou l'abandonner.")


def _probe_updates(report: _Report) -> None:
    from app.utils import tor_proxy
    from app.updates import orchestrator as update_orchestrator

    status = update_orchestrator.get_status()
    if status.get("step") == "failed":
        report.problem("updates", "update_failed", "critical", f"La dernière mise à jour a échoué : {status.get('error') or 'cause inconnue'}.",
                       "Consulter le journal technique puis relancer la mise à jour depuis Réglages.")
    if tor_proxy.is_enabled():
        report.check("tor", "not_checked", "Tor actif pour les mises à jour : POST /api/updates/tor-check pour le tester")


def _probe_media_native(report: _Report) -> None:
    from app.utils import media_native

    state = media_native.status()
    if state.get("enabled") and state.get("state") in ("fallback", "absent"):
        report.problem("media_native", "media_native_fallback", "info",
                       "Le composant audio natif est activé mais inutilisé : ffmpeg prend le relais.",
                       "Désactiver le composant natif dans Réglages, ou réinstaller Bobine.",
                       fix={"action": "set_settings", "settings": {"media_native": "false"}})


async def _probe_storage(report: _Report) -> None:
    from app.storage.service import service as storage_service

    try:
        status = await storage_service.status()
    except Exception as exc:  # noqa: BLE001
        report.check("storage", "unknown", f"{type(exc).__name__}: {exc}")
        return
    error = status.get("error")
    if error:
        detail = error.get("message") if isinstance(error, dict) else str(error)
        report.problem("storage", "storage_driver_error", "warning", f"Supports externes : {detail}.",
                       "Vérifier le service de montage du système et les droits de Bobine sur les supports.")
    else:
        report.check("storage", "ok")


@router.get("/system")
async def system_diagnostics() -> dict:
    """État de santé de Bobine : `status` (`ok`, `warning`, `critical`, ou `unknown` si une sonde n'a pas pu répondre
    sans qu'aucun problème soit trouvé), `problems` triés par gravité, chacun
    `{code, severity, message, remedy}` avec un code stable, et `checks` (chaque sonde, même saine)."""
    from datetime import datetime, timezone

    from fastapi.concurrency import run_in_threadpool

    report = _Report()

    def synchronous_probes() -> None:
        for name, function in (
            ("database", _probe_database), ("kiosk", _probe_kiosk), ("port", _probe_port), ("network", _probe_network),
            ("media_tools", _probe_media_tools), ("disk", _probe_disks), ("imports", _probe_imports),
            ("updates", _probe_updates), ("media_native", _probe_media_native), ("firewall", _probe_firewall),
        ):
            report.probe(name, function)

    await run_in_threadpool(synchronous_probes)
    await _probe_storage(report)
    report.problems.sort(key=lambda p: SEVERITIES.index(p["severity"]))
    severities = {p["severity"] for p in report.problems}
    status = "critical" if "critical" in severities else "warning" if "warning" in severities else "ok"
    if status == "ok" and any(check["status"] == "unknown" for check in report.checks):
        # Aucun problème trouvé, mais au moins une sonde n'a pas pu répondre : « ok » serait une affirmation fausse.
        status = "unknown"
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "status": status,
        "problems": report.problems,
        "checks": report.checks,
    }

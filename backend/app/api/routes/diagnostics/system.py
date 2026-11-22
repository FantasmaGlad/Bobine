"""Diagnostic du système : base, écrans, réseau, outils, disques, mises à jour et stockage."""

import logging
import tempfile
from typing import Any, Callable

from fastapi import APIRouter

from app.utils import ffmpeg_binaries

from .imports import LOW_DISK_BYTES, STUCK_JOB_SECONDS, directory_state, executor_state, jobs_state, staging_state

logger = logging.getLogger(__name__)

router = APIRouter()


SEVERITIES = ("critical", "warning", "info")


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
        """`fix` (facultatif) décrit une correction sans risque que `bobine diagnose --auto-fix` peut appliquer."""
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
        except Exception as exc:
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
    except Exception as exc:
        report.problem("database", "database_unreachable", "critical", f"La base de données ne répond pas ({exc}).",
                       "Vérifier le fichier de la base, ses droits et l'espace disque, puis redémarrer Bobine.")


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

    temp = directory_state(tempfile.gettempdir())
    if not temp["exists"] or not temp["writable"]:
        report.problem("disk", "temp_not_writable", "critical", "Le dossier temporaire des imports n'est pas inscriptible.",
                       "Corriger les droits du dossier temporaire ou libérer de la place.")
    elif isinstance(temp["free_bytes"], int) and temp["free_bytes"] < LOW_DISK_BYTES:
        report.problem("disk", "disk_low", "critical", "Moins de 2 Go libres pour les imports.",
                       "Supprimer des médias inutilisés ou déplacer les données vers un disque plus grand.")
    media = directory_state(settings.media_dir)
    if isinstance(media["free_bytes"], int) and media["free_bytes"] < LOW_MEDIA_DISK_BYTES:
        report.problem("disk", "disk_low_media", "warning", "Moins de 5 Go libres sur le disque des médias.",
                       "Supprimer des médias inutilisés ou ajouter un support externe.")


def _probe_imports(report: _Report) -> None:
    jobs = jobs_state()
    stuck = [j for j in jobs["active"] if j["idle_seconds"] > STUCK_JOB_SECONDS]
    if stuck:
        report.problem("imports", "import_job_stuck", "warning", f"{len(stuck)} import(s) sans progression depuis plus de 5 minutes.",
                       "Annuler l'import concerné puis consulter le journal technique.",
                       fix={"action": "cancel_import_jobs", "job_ids": [j["job_id"] for j in stuck]})
    if executor_state()["ffmpeg"]["shutdown"]:
        report.problem("imports", "import_executor_shutdown", "critical", "Le moteur de traitement des médias est arrêté.",
                       "Redémarrer Bobine.")
    staging = staging_state()
    if staging.get("partial_uploads"):
        report.problem("imports", "staged_uploads_pending", "info",
                       f"{staging['partial_uploads']} transfert(s) inachevé(s) en attente de reprise.",
                       "Reprendre le transfert depuis la page d'import, ou l'abandonner.")


def _probe_updates(report: _Report) -> None:
    from app.updates import orchestrator as update_orchestrator

    status = update_orchestrator.get_status()
    if status.get("step") == "failed":
        report.problem("updates", "update_failed", "critical", f"La dernière mise à jour a échoué : {status.get('error') or 'cause inconnue'}.",
                       "Consulter le journal technique puis relancer la mise à jour depuis Réglages.")


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
    except Exception as exc:
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
    """État de santé de Bobine : `status` (`ok`, `warning`, `critical`, ou `unknown` si une sonde n'a pas pu répondre sans qu'aucun problème soit trouvé), `problems` triés par gravité, chacun `{code, severity, message, remedy}` avec un code stable, et `checks` (chaque sonde, même saine)."""
    from datetime import datetime, timezone

    from fastapi.concurrency import run_in_threadpool

    report = _Report()

    def synchronous_probes() -> None:
        for name, function in (
            ("database", _probe_database), ("port", _probe_port), ("network", _probe_network),
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
        status = "unknown"
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "status": status,
        "problems": report.problems,
        "checks": report.checks,
    }

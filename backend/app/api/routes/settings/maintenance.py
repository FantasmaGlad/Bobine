"""Occupation du stockage, purge des journaux, redémarrage, réinitialisation, désinstallation, ouverture d'un dossier."""

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import (
    DATA_DIRS,
    settings as runtime_settings,
)
from app.database import get_db
from app.hardware.disk import get_storage_model
from app.hardware.telemetry import get_system_telemetry_payload, purge_expired_logs_and_metrics
from app.models import Setting
from app.utils.activity_log import log_activity
from app.utils.android_runtime import is_android
from app.utils.deployment import (
    SUDOERS_FILE,
    UNINSTALL_WRAPPER,
    get_profile_handler,
)
from app.utils.ws_manager import manager as ws_manager

from .core import router
from app.api.responses import OpenedPath

logger = logging.getLogger(__name__)


def _dir_size(path: Path) -> int:
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += _dir_size(Path(entry.path))
                except OSError:
                    continue
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return 0
    return total


@router.get("/storage")
def get_storage() -> dict[str, Any]:
    """Indicateur de capacité de stockage : espace disque du volume qui héberge les médias (total / utilisé / libre) et empreinte propre de l'application (somme des dossiers de médias)."""
    media_dir = Path(runtime_settings.media_dir)
    probe = media_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        usage = shutil.disk_usage(probe)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Impossible de lire l'espace disque : {e}")

    app_bytes = 0
    seen: set[str] = set()
    for attr in DATA_DIRS:
        raw = getattr(runtime_settings, attr, None)
        if not raw:
            continue
        resolved = str(Path(raw))
        if resolved in seen:
            continue
        seen.add(resolved)
        app_bytes += _dir_size(Path(raw))

    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
        "used_percent": round(usage.used / usage.total * 100, 1) if usage.total else 0.0,
        "app_bytes": app_bytes,
        "path": str(probe),
        "storage_model": get_storage_model(),
    }


@router.get("/system")
def get_system_usage() -> dict[str, Any]:
    """Charge CPU, GPU, RAM, Températures, Puissance (W), Modèles des composants et Runtime."""
    return get_system_telemetry_payload()


@router.post("/logs/purge")
def purge_logs_manual(retention_days: int | None = None, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Purge manuelle des journaux d'activité et historiques de métriques."""
    if retention_days is None:
        row = db.query(Setting).filter(Setting.key == "logs_retention_days").first()
        retention_days = int(row.value) if row and row.value and row.value.isdigit() else 7
    if retention_days < 1:
        retention_days = 1
    purged = purge_expired_logs_and_metrics(db, retention_days)
    log_activity(
        db,
        "logs_purged",
        f"Purge manuelle (rétention {retention_days}j) : {purged['purged_logs']} logs, {purged['purged_metrics']} métriques",
    )
    return {"message": "Purge effectuée avec succès", "details": purged, "retention_days": retention_days}


async def _run_full_reset():
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec de la diffusion force_reload : {e}")

    await asyncio.sleep(1.0)

    get_profile_handler().restart_services()


async def _run_restart():
    await asyncio.sleep(1.0)
    get_profile_handler().restart_services()


@router.post("/system/restart")
async def restart_system(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Redémarrage simple (sans effacer de données), par exemple pour appliquer un changement de langue."""
    log_activity(db, "settings", "Redémarrage demandé")
    background_tasks.add_task(_run_restart)
    return {"status": "restarting", "restart_guaranteed": get_profile_handler().restart_is_guaranteed()}


@router.post("/system/reset")
async def reset_system(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Réinitialisation complète : force le rechargement de tous les écrans connectés puis redémarre le kiosk et le backend."""
    background_tasks.add_task(_run_full_reset)
    return {"message": "Synchronisation en cours : les écrans vident leur cache et rechargent les nouveaux assets."}


class UninstallRequest(BaseModel):
    confirm: str


async def _run_uninstall():
    await asyncio.sleep(1.0)
    try:
        get_profile_handler().start_uninstall()
    except Exception as e:
        logger.error(f"Échec du lancement de la désinstallation : {e}")


@router.post("/system/uninstall")
async def uninstall_system(payload: UninstallRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
    """Remise à zéro complète de la machine."""
    phrase = payload.confirm.strip().upper().replace("É", "E")
    if phrase != "DESINSTALLER":
        raise HTTPException(status_code=422, detail="Phrase de confirmation incorrecte.")

    handler = get_profile_handler()
    if not handler.can_self_uninstall():
        return {"message": handler.uninstall_instructions(), "self_uninstall": "false"}

    if handler.profile == "linux-headless" and (not UNINSTALL_WRAPPER.exists() or not SUDOERS_FILE.exists()):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cette machine n'est pas une installation gérée (désinstalleur système absent). "
                "Depuis un poste de dev, lancez à la main : sudo ./install.sh --uninstall --purge --purge-data"
            ),
        )
    background_tasks.add_task(_run_uninstall)
    return {"message": "Désinstallation lancée : la procédure de suppression est en cours d'exécution."}


class OpenPathRequest(BaseModel):
    path: str


_OPENABLE_DIR_FIELDS = (
    "media_dir", "watch_dir", "thumbnails_dir", "backgrounds_dir", "backgrounds_watch_dir",
    "audio_dir", "audio_watch_dir", "radio_dir", "radio_watch_dir", "radio_covers_dir",
    "radio_announcements_dir", "branding_dir", "logs_dir", "subtitles_dir",
)


def _openable_roots() -> list[Path]:
    roots = [Path(getattr(runtime_settings, field)).resolve() for field in _OPENABLE_DIR_FIELDS]
    db_url = runtime_settings.database_url
    if db_url.startswith("sqlite:///"):
        roots.append(Path(db_url[len("sqlite:///"):]).resolve().parent)
    return roots


@router.post("/open-path", response_model=OpenedPath)
def open_path(payload: OpenPathRequest):
    """Ouvre un dossier de données Bobine dans le gestionnaire de fichiers natif de l'OS (xdg-open, explorer, open)."""
    raw_path = payload.path.strip()
    if raw_path.startswith("sqlite:///"):
        raw_path = raw_path[len("sqlite:///"):]
    target = Path(raw_path).expanduser().resolve()
    if target.is_file():
        target = target.parent

    if not any(target == root or root in target.parents for root in _openable_roots()):
        raise HTTPException(status_code=403, detail="Ce chemin n'est pas un dossier de données de Bobine")
    if not target.is_dir():
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    if is_android():
        return {
            "status": "android",
            "path": str(target),
            "message": "Chemin système Android copié. Accessible via une application de gestion de fichiers ou connexion USB (MTP).",
        }

    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            os.startfile(str(target))
        return {"status": "ok", "path": str(target)}
    except Exception as e:
        logger.warning("Échec de l'ouverture du dossier %s : %s", target, e)
        raise HTTPException(status_code=500, detail=f"Impossible d'ouvrir le gestionnaire de fichiers : {e}")

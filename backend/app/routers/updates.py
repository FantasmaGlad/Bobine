import asyncio
import json
import logging
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.utils.activity_log import log_activity
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/updates", tags=["updates"])

GITHUB_REPO = "FantasmaGlad/Bobine"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
BACKEND_SERVICE_UNIT = "bobine-backend.service"
KIOSK_SERVICE_UNIT = "bobine-kiosk.service"


def _parse_semver(version_str: str) -> tuple[int, ...]:
    """Extrait les nombres d'une chaîne de version (ex: 'V2.0.1' -> (2, 0, 1))."""
    numbers = re.findall(r"\d+", version_str or "")
    return tuple(map(int, numbers)) if numbers else (0, 0, 0)


def _get_local_version_info() -> dict[str, str]:
    """Détermine la version et le commit locaux depuis Git ou valeurs par défaut."""
    repo_dir = Path(__file__).resolve().parent.parent.parent
    commit = "unknown"
    tag = "V2.0.1"

    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        commit = res.stdout.strip()
    except Exception:
        pass

    try:
        res = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
        tag = res.stdout.strip()
    except Exception:
        pass

    # Version de base (ex: 'V2.0.1-10-gfedd080' -> 'V2.0.1')
    base_version = tag.split("-")[0] if "-" in tag else tag
    if not base_version.upper().startswith("V"):
        base_version = f"V{base_version}"

    return {
        "current_version": base_version,
        "current_tag": tag,
        "current_commit": commit,
    }


@router.get("/check")
async def check_updates() -> dict[str, Any]:
    """
    Vérifie la disponibilité d'une nouvelle release officielle sur GitHub.
    Gère gracieusement le mode hors-ligne sans planter.
    """
    local_info = _get_local_version_info()
    now_iso = datetime.now(timezone.utc).isoformat()

    req = urllib.request.Request(
        GITHUB_API_URL,
        headers={
            "User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)",
            "Accept": "application/vnd.github+json",
        },
    )

    loop = asyncio.get_running_loop()

    def _fetch_github() -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.info(f"Vérification GitHub indisponible (mode hors-ligne ou timeout) : {e}")
            return None
        return None

    release_data = await loop.run_in_executor(None, _fetch_github)

    if not release_data:
        return {
            "online": False,
            "current_version": local_info["current_version"],
            "current_tag": local_info["current_tag"],
            "current_commit": local_info["current_commit"],
            "latest_version": None,
            "has_update": False,
            "release_title": None,
            "release_notes": None,
            "published_at": None,
            "html_url": None,
            "message": "Impossible de contacter les serveurs de mise à jour (hors ligne ou indisponible).",
            "checked_at": now_iso,
        }

    latest_tag = release_data.get("tag_name") or ""
    release_title = release_data.get("name") or latest_tag
    release_notes = release_data.get("body") or ""
    published_at = release_data.get("published_at") or ""
    html_url = release_data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"

    # Comparaison sémantique
    local_semver = _parse_semver(local_info["current_version"])
    latest_semver = _parse_semver(latest_tag)

    has_update = latest_semver > local_semver

    return {
        "online": True,
        "current_version": local_info["current_version"],
        "current_tag": local_info["current_tag"],
        "current_commit": local_info["current_commit"],
        "latest_version": latest_tag,
        "has_update": has_update,
        "release_title": release_title,
        "release_notes": release_notes,
        "published_at": published_at,
        "html_url": html_url,
        "checked_at": now_iso,
    }


async def _run_update_pipeline():
    """Tâche d'arrière-plan appliquant la mise à jour Git et redémarrant les services."""
    repo_dir = Path(__file__).resolve().parent.parent.parent
    logger.info("Début du processus de mise à jour système...")

    try:
        # 1. Pull Git
        res = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=45,
        )
        logger.info(f"git pull résultat : {res.stdout}")
    except Exception as e:
        logger.error(f"Erreur lors du git pull de mise à jour : {e}")
        return

    # 2. Diffusion de rafraîchissement
    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec broadcast WebSocket lors de la mise à jour : {e}")

    await asyncio.sleep(1.0)

    # 3. Redémarrage des services systemd si disponibles
    for unit in (KIOSK_SERVICE_UNIT, BACKEND_SERVICE_UNIT):
        try:
            subprocess.run(["sudo", "systemctl", "restart", unit], check=True, timeout=20)
            logger.info(f"Service {unit} redémarré après mise à jour.")
        except Exception as e:
            logger.info(f"Redémarrage systemd {unit} ignoré (environnement dev ?) : {e}")


@router.post("/apply")
async def apply_update(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Déclenche la mise à jour du système et le rechargement des services."""
    background_tasks.add_task(_run_update_pipeline)
    return {
        "status": "started",
        "message": "Téléchargement et application de la mise à jour en cours...",
    }

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
from app.utils.deployment import (
    UpdateUnsupported,
    get_deployment_profile,
    get_profile_handler,
)
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/updates", tags=["updates"])

GITHUB_REPO = "FantasmaGlad/Bobine"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_semver(version_str: str) -> tuple[int, ...]:
    """Extrait les nombres d'une chaîne de version (ex: 'V3.0.0' -> (3, 0, 0))."""
    numbers = re.findall(r"\d+", version_str or "")
    return tuple(map(int, numbers)) if numbers else (0, 0, 0)


def _get_local_version_info() -> dict[str, str]:
    """Détermine la version et le commit locaux depuis Git ou valeurs par défaut.

    N'exécute `git` que sur les profils dont le dossier d'installation est
    un vrai checkout (aujourd'hui : l'appliance headless seule) — un paquet
    figé (`.exe`, `.app`, `.deb`) n'a pas de `.git` et ces appels
    échoueraient systématiquement en pure perte (deux sous-process, jusqu'à
    3s de timeout chacun, à chaque chargement de la page Réglages)."""
    commit = "unknown"
    tag = "V3.0.0"

    if not get_profile_handler().supports_git_versioning():
        return {"current_version": tag, "current_tag": tag, "current_commit": commit}

    repo_dir = Path(__file__).resolve().parent.parent.parent
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

    # Version de base (ex: 'V3.0.0-10-gfedd080' -> 'V3.0.0')
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

    profile = get_deployment_profile()
    handler = get_profile_handler()

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
            "can_auto_apply": handler.supports_git_versioning(),
            "download_url": None,
            "asset_name": None,
            "asset_size": None,
            "deployment_profile": profile,
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
    can_auto_apply = handler.supports_git_versioning()

    # Recherche de l'asset adapté au profil de déploiement (Lot 1 Windows .exe,
    # Lot 2 Linux bureau .deb, Lot 3 macOS .dmg)
    assets = release_data.get("assets") or []
    matched_asset = None
    target_ext = None
    if profile == "windows":
        target_ext = ".exe"
    elif profile == "linux-desktop":
        target_ext = ".deb"
    elif profile == "macos":
        target_ext = ".dmg"

    if target_ext:
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(target_ext):
                matched_asset = asset
                break

    download_url = matched_asset.get("browser_download_url") if matched_asset else html_url
    asset_name = matched_asset.get("name") if matched_asset else None
    asset_size = matched_asset.get("size") if matched_asset else None

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
        "can_auto_apply": can_auto_apply,
        "download_url": download_url,
        "asset_name": asset_name,
        "asset_size": asset_size,
        "deployment_profile": profile,
        "checked_at": now_iso,
    }


async def _run_update_pipeline():
    """Tâche d'arrière-plan appliquant la mise à jour et redémarrant les
    services, via le handler du profil courant (§5.1/§5.4 du plan). Le
    garde-fou de `apply_update()` (endpoint ci-dessous) évite normalement
    d'arriver ici sur un profil qui ne supporte pas encore ce pipeline ;
    l'exception est quand même rattrapée par prudence."""
    logger.info("Début du processus de mise à jour système...")

    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec broadcast WebSocket lors de la mise à jour : {e}")

    await asyncio.sleep(1.0)

    try:
        get_profile_handler().apply_update()
    except UpdateUnsupported as e:
        logger.warning(f"Mise à jour non applicable sur ce profil : {e.message}")
    except Exception as e:
        logger.error(f"Erreur lors de l'application de la mise à jour : {e}")


@router.post("/apply")
async def apply_update(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Déclenche la mise à jour du système et le rechargement des services.

    Non disponible sur les profils sans checkout git réel (Windows, et plus
    tard macOS/Linux de bureau — cf. CDC §12, mécanisme non cadré pour ces
    profils) : renvoie 400 avec un message clair plutôt que de démarrer un
    pipeline qui échouerait silencieusement en tâche de fond."""
    if not get_profile_handler().supports_git_versioning():
        raise HTTPException(
            status_code=400,
            detail=(
                "La mise à jour automatique n'est pas encore disponible sur ce profil — "
                "téléchargez la dernière version depuis les releases GitHub du projet."
            ),
        )
    background_tasks.add_task(_run_update_pipeline)
    return {
        "status": "started",
        "message": "Téléchargement et application de la mise à jour en cours...",
    }

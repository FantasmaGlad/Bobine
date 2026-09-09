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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    UpdateUnsupported,
    get_deployment_profile,
    get_profile_handler,
)
from app.utils.version import get_app_commit, get_app_tag
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/updates", tags=["updates"])

GITHUB_REPO = "FantasmaGlad/Bobine"
# "stable" n'interroge QUE /releases/latest, qui exclut structurellement les
# pre-releases et brouillons côté API GitHub — aucun risque qu'un canal
# stable voie jamais une bêta, même en cas de bug côté filtrage applicatif.
# "beta" interroge un tag FIXE ("beta") — un seul fichier de release Bêta
# sur GitHub, republié en place à chaque build plutôt qu'un nouveau tag par
# itération (réf. mission "canal Stable/Bêta" — éviter l'accumulation de
# releases sur la page publique). Voir .github/workflows/ci.yml, job
# `release-beta` : force-déplace ce tag et republie dessus à chaque
# déclenchement manuel.
_RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_RELEASES_BETA_TAG_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/beta"
_VALID_CHANNELS = ("stable", "beta")


def _get_update_channel(db: Session) -> str:
    row = db.query(Setting).filter(Setting.key == "update_channel").first()
    channel = row.value if row else None
    return channel if channel in _VALID_CHANNELS else "stable"


def _parse_version(version_str: str) -> tuple[tuple[int, int, int], tuple]:
    """Parse une chaîne 'V3.0.1' ou 'V3.0.1-beta.2' en clé de tri conforme à
    la précédence semver : à base MAJOR.MINOR.PATCH égale, une version SANS
    pre-release est toujours postérieure à une version AVEC pre-release, et
    deux pre-releases se comparent identifiant par identifiant (numérique si
    possible, sinon lexical — les identifiants numériques ont une précédence
    inférieure aux alphanumériques, cf. spec semver §11). Remplace l'ancien
    `_parse_semver`, qui comparait des tuples d'entiers bruts et ne
    distinguait pas 'V3.0.1-beta.1' de 'V3.0.1-beta.2' (les deux valaient
    (3, 0, 1, 1) et (3, 0, 1, 2) par accident de parsing, et une vraie
    'V3.0.1' stable pouvait même être vue comme ANTÉRIEURE à une bêta portant
    un numéro d'identifiant plus élevé)."""
    s = (version_str or "").strip()
    if s[:1] in ("v", "V"):
        s = s[1:]
    base_part, _, prerelease_part = s.partition("-")
    base_numbers = [int(n) for n in re.findall(r"\d+", base_part)[:3]]
    base_numbers += [0] * (3 - len(base_numbers))
    base = (base_numbers[0], base_numbers[1], base_numbers[2])

    if not prerelease_part:
        return base, (1,)

    parsed_ids: tuple = tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in prerelease_part.split(".")
        if part
    )
    return base, (0, *parsed_ids)


def _get_local_version_info() -> dict[str, str]:
    """Détermine la version et le commit locaux depuis Git ou valeurs par défaut.

    N'exécute `git` que sur les profils dont le dossier d'installation est
    un vrai checkout (aujourd'hui : l'appliance headless seule) — un paquet
    figé (`.exe`, `.app`, `.deb`) n'a pas de `.git` et ces appels
    échoueraient systématiquement en pure perte (deux sous-process, jusqu'à
    3s de timeout chacun, à chaque chargement de la page Réglages). Ces
    profils lisent en revanche le commit depuis le fichier COMMIT bundlé par
    la CI (`get_app_commit()`, réf. mission "canal Stable/Bêta") — nécessaire
    pour que la détection de mise à jour du canal Bêta (comparaison de
    commit, cf. `_beta_has_update`) fonctionne aussi sur les profils
    packagés, pas seulement sur l'appliance headless."""
    commit = get_app_commit()
    tag = get_app_tag()

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


async def _fetch_release_for_channel(channel: str) -> dict[str, Any] | None:
    """Interroge GitHub pour le canal donné — partagé entre `check_updates()`
    (affichage) et `apply_update()` (résolution du tag cible pour
    `apply_update(target_tag=...)`), pour ne jamais risquer que les deux
    endpoints déterminent une release différente. Un seul objet release dans
    les deux cas (`/releases/latest` pour stable, `/releases/tags/beta` pour
    bêta) — même forme de réponse, pas de liste à filtrer côté application."""
    url = _RELEASES_BETA_TAG_URL if channel == "beta" else _RELEASES_LATEST_URL
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)",
            "Accept": "application/vnd.github+json",
        },
    )

    loop = asyncio.get_running_loop()

    def _fetch_github() -> dict[str, Any] | None:
        try:
            with urllib.request.urlopen(req, timeout=4.5) as resp:
                if resp.status != 200:
                    return None
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.info(f"Vérification GitHub indisponible (mode hors-ligne ou timeout) : {e}")
            return None

    return await loop.run_in_executor(None, _fetch_github)


def _short(sha: str | None, length: int = 7) -> str:
    return (sha or "")[:length]


def _beta_has_update(local_commit: str, release_data: dict[str, Any]) -> bool:
    """Le canal Bêta n'a pas de numéro de version qui avance à chaque build
    (tag fixe "beta", réf. mission "canal Stable/Bêta") — la comparaison
    porte donc sur le COMMIT plutôt que sur une version sémantique : y a-t-il
    une mise à jour si le commit visé par le tag "beta" diffère du commit
    actuellement installé. `target_commitish` d'une release GitHub créée sur
    un tag léger est le SHA complet pointé par ce tag."""
    remote_commit = _short(release_data.get("target_commitish"))
    if not remote_commit or local_commit in ("unknown", ""):
        return False
    return not remote_commit.startswith(local_commit) and not local_commit.startswith(remote_commit)


@router.get("/check")
async def check_updates(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Vérifie la disponibilité d'une nouvelle release officielle sur GitHub,
    en respectant le canal choisi dans Réglages → Mises à jour (Stable ou
    Bêta, "Programme Bobine Beta" — cf. `_get_update_channel`).
    Gère gracieusement le mode hors-ligne sans planter.
    """
    local_info = _get_local_version_info()
    now_iso = datetime.now(timezone.utc).isoformat()
    channel = _get_update_channel(db)

    release_data = await _fetch_release_for_channel(channel)

    profile = get_deployment_profile()
    handler = get_profile_handler()

    if not release_data:
        return {
            "online": False,
            "channel": channel,
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

    if channel == "beta":
        has_update = _beta_has_update(local_info["current_commit"], release_data)
        remote_short = _short(release_data.get("target_commitish"))
        # Affichage informatif (pas de numéro de version qui avance à chaque
        # build sur ce canal, cf. _beta_has_update) : le commit visé plutôt
        # qu'un numéro de version qui resterait figé entre deux publications.
        latest_version = f"beta ({remote_short})" if remote_short else "beta"
    else:
        has_update = _parse_version(latest_tag) > _parse_version(local_info["current_version"])
        latest_version = latest_tag
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
    elif profile == "android":
        # Lot 11 : aucun asset .apk n'existe encore sur les releases
        # publiques (Lot 13, publication volontairement differee) - ce
        # cas reste donc inerte (repli sur html_url) tant que cette
        # decision n'est pas revisitee, mais prepare le terrain pour
        # qu'un .apk publie plus tard soit detecte automatiquement, sans
        # nouveau changement ici.
        target_ext = ".apk"

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
        "channel": channel,
        "current_version": local_info["current_version"],
        "current_tag": local_info["current_tag"],
        "current_commit": local_info["current_commit"],
        "latest_version": latest_version,
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


async def _run_update_pipeline(target_tag: str | None):
    """Tâche d'arrière-plan appliquant la mise à jour et redémarrant les
    services, via le handler du profil courant (§5.1/§5.4 du plan). Le
    garde-fou de `apply_update()` (endpoint ci-dessous) évite normalement
    d'arriver ici sur un profil qui ne supporte pas encore ce pipeline ;
    l'exception est quand même rattrapée par prudence. `target_tag` épingle
    le checkout sur le tag résolu par le canal courant au moment du clic
    (réf. mission "canal Stable/Bêta") — None si la résolution GitHub a
    échoué, auquel cas le handler retombe sur son ancien comportement
    (`git pull --ff-only` sur la branche courante)."""
    logger.info(f"Début du processus de mise à jour système (cible : {target_tag or 'branche courante'})...")

    try:
        await ws_manager.broadcast_force_reload()
    except Exception as e:
        logger.warning(f"Échec broadcast WebSocket lors de la mise à jour : {e}")

    await asyncio.sleep(1.0)

    try:
        get_profile_handler().apply_update(target_tag)
    except UpdateUnsupported as e:
        logger.warning(f"Mise à jour non applicable sur ce profil : {e.message}")
    except Exception as e:
        logger.error(f"Erreur lors de l'application de la mise à jour : {e}")


@router.post("/apply")
async def apply_update(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, str]:
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
    # Résout à nouveau la release cible au moment du clic (plutôt que de
    # faire confiance à une valeur envoyée par le client) : reflète toujours
    # le canal Stable/Bêta courant, y compris si l'utilisateur l'a changé
    # entre le dernier "Rechercher une mise à jour" et ce clic.
    channel = _get_update_channel(db)
    release_data = await _fetch_release_for_channel(channel)
    target_tag = (release_data or {}).get("tag_name") or None
    background_tasks.add_task(_run_update_pipeline, target_tag)
    return {
        "status": "started",
        "message": "Téléchargement et application de la mise à jour en cours...",
    }

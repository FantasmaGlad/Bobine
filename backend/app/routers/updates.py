import asyncio
import json
import logging
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
    get_deployment_profile,
    get_profile_handler,
)
from app.utils.update_orchestrator import (
    get_status,
    is_running,
    report_external_event,
    run_update_pipeline,
)
from app.utils.version import get_app_commit, get_app_tag

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

# Extension d'asset attendue par profil de déploiement — un seul point de
# vérité, utilisé à la fois par `check_updates()` (affichage) et
# `apply_update()` (résolution de l'URL à télécharger), qui dupliquaient
# auparavant chacun leur propre copie de ce mapping.
_ASSET_EXTENSION_BY_PROFILE = {
    "windows": ".exe",
    "linux-desktop": ".deb",
    "macos": ".dmg",
    "android": ".apk",
}


class AndroidUpdateCallback(BaseModel):
    """Rappel émis par `UpdateManager.kt` une fois le téléchargement de
    l'APK terminé (succès ou échec) — `apply_update()` du profil Android
    (backend/app/utils/deployment_profiles/android.py) délègue le
    téléchargement à un thread Kotlin asynchrone et ne peut donc pas
    connaître l'issue réelle avant que ce rappel n'arrive."""

    status: str  # "downloaded" ou "error"
    message: str | None = None


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
    inférieure aux alphanumériques, cf. spec semver §11)."""
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
    échoueraient systématiquement en pure perte."""
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

    # Si le tag résolu n'est pas un semver valide (ex: simple SHA de commit
    # '92e2c85' en cas de clone superficiel shallow/CI sans fetch des tags),
    # repli systématique sur la source de vérité VERSION/get_app_tag().
    if not re.match(r"^V?\d+(\.\d+)+", base_version, re.IGNORECASE):
        base_version = get_app_tag()

    return {
        "current_version": base_version,
        "current_tag": tag,
        "current_commit": commit,
    }


async def _fetch_release_for_channel(channel: str) -> dict[str, Any] | None:
    """Interroge GitHub pour le canal donné — partagé entre `check_updates()`
    (affichage) et `apply_update()` (résolution du tag cible), pour ne
    jamais risquer que les deux endpoints déterminent une release
    différente."""
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
    (tag fixe "beta") — la comparaison porte donc sur le COMMIT plutôt que
    sur une version sémantique."""
    remote_commit = _short(release_data.get("target_commitish"))
    if not remote_commit or local_commit in ("unknown", ""):
        return False
    return not remote_commit.startswith(local_commit) and not local_commit.startswith(remote_commit)


def _resolve_asset(profile: str, release_data: dict[str, Any] | None) -> dict[str, Any]:
    """Cherche l'asset adapté au profil de déploiement courant parmi ceux
    d'une release GitHub. Renvoie systématiquement les quatre mêmes clés
    (valant `None` si aucun asset ne correspond), pour que les deux
    appelants (`check_updates`, `apply_update`) n'aient chacun qu'une seule
    forme de résultat à gérer. `digest` reprend le champ natif que l'API
    GitHub Releases fournit déjà pour chaque asset (`"sha256:<hex>"`) —
    aucune infrastructure de checksum supplémentaire n'est nécessaire pour
    vérifier l'intégrité d'un téléchargement avant de l'exécuter avec des
    privilèges élevés (cf. `update_orchestrator.download_with_progress`)."""
    target_ext = _ASSET_EXTENSION_BY_PROFILE.get(profile)
    assets = (release_data or {}).get("assets") or []
    matched = None
    if target_ext:
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(target_ext):
                matched = asset
                break
    return {
        "download_url": matched.get("browser_download_url") if matched else None,
        "asset_name": matched.get("name") if matched else None,
        "asset_size": matched.get("size") if matched else None,
        "asset_digest": matched.get("digest") if matched else None,
    }


@router.get("/check")
async def check_updates(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Vérifie la disponibilité d'une nouvelle release officielle sur GitHub,
    en respectant le canal choisi dans Réglages → Mises à jour (Stable ou
    Bêta). Gère gracieusement le mode hors-ligne sans planter.
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
            "can_auto_apply": handler.can_auto_apply(),
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
        # build sur ce canal) : le commit visé plutôt qu'un numéro de
        # version qui resterait figé entre deux publications.
        latest_version = f"beta ({remote_short})" if remote_short else "beta"
    else:
        has_update = _parse_version(latest_tag) > _parse_version(local_info["current_version"])
        latest_version = latest_tag

    asset = _resolve_asset(profile, release_data)
    download_url = asset["download_url"] or html_url

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
        "can_auto_apply": handler.can_auto_apply(),
        "download_url": download_url,
        "asset_name": asset["asset_name"],
        "asset_size": asset["asset_size"],
        "deployment_profile": profile,
        "checked_at": now_iso,
    }


@router.get("/status")
async def get_update_status() -> dict[str, Any]:
    """État courant (ou dernier connu) du pipeline de mise à jour — lu par
    le frontend au chargement de la page ET par l'overlay de progression
    en repli si le WebSocket n'est pas connecté au moment où une mise à
    jour planifiée se termine (cas concret : déclenchement à 3h du matin,
    personne devant l'écran)."""
    return get_status()


@router.post("/_android-callback")
async def android_update_callback(payload: AndroidUpdateCallback) -> dict[str, str]:
    """Rappel interne (boucle locale uniquement, jamais exposé au delà de
    127.0.0.1 par la configuration réseau du profil Android) : `UpdateManager.
    kt` l'appelle une fois le téléchargement de l'APK terminé, puisque
    `apply_update()` côté Python ne peut pas connaître cette issue avant
    que le thread Kotlin ne l'ait déterminée."""
    if payload.status == "downloaded":
        await report_external_event(
            "awaiting_user_confirmation",
            message=payload.message or "APK téléchargé — confirmez l'installation sur l'appareil.",
        )
    else:
        await report_external_event("failed", message=payload.message, error=payload.message)
    return {"status": "ok"}


@router.post("/apply")
async def apply_update(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, str]:
    """Déclenche la mise à jour du système en tâche de fond.

    Vérifie si le profil de déploiement supporte l'application automatique
    et qu'aucune mise à jour n'est déjà en cours (409 sinon — corrige le
    risque de deux installations concurrentes sur un double clic ou deux
    onglets ouverts)."""
    handler = get_profile_handler()
    if not handler.can_auto_apply():
        raise HTTPException(
            status_code=400,
            detail=(
                "La mise à jour automatique n'est pas encore disponible sur ce profil — "
                "téléchargez la dernière version depuis les releases GitHub du projet."
            ),
        )
    if is_running():
        raise HTTPException(status_code=409, detail="Une mise à jour est déjà en cours d'application.")

    # Résout à nouveau la release cible au moment du clic (plutôt que de
    # faire confiance à une valeur envoyée par le client) : reflète toujours
    # le canal Stable/Bêta courant, y compris si l'utilisateur l'a changé
    # entre le dernier "Rechercher une mise à jour" et ce clic.
    channel = _get_update_channel(db)
    release_data = await _fetch_release_for_channel(channel)
    target_tag = (release_data or {}).get("tag_name") or None

    profile = get_deployment_profile()
    asset = _resolve_asset(profile, release_data)

    log_activity(db, "update_apply", f"Mise à jour manuelle déclenchée (cible : {target_tag or 'branche courante'})")
    background_tasks.add_task(
        run_update_pipeline, target_tag, asset["download_url"], asset["asset_digest"], "manual"
    )
    return {
        "status": "started",
        "message": "Téléchargement et application de la mise à jour en cours...",
    }


async def run_scheduled_update_if_available(db: Session) -> None:
    """Appelée par `scheduler_manager` au créneau planifié (Réglages → Mise
    à jour automatique). Vérifie d'abord qu'une mise à jour existe RÉELLEMENT
    avant de déclencher quoi que ce soit — contrairement au bouton manuel,
    personne ne clique ici, donc pas de retour utilisateur immédiat en cas
    de "rien à faire" à gérer, juste un silence normal dans les journaux."""
    handler = get_profile_handler()
    if not handler.can_schedule_auto_apply() or is_running():
        return
    channel = _get_update_channel(db)
    release_data = await _fetch_release_for_channel(channel)
    if not release_data:
        return
    local_info = _get_local_version_info()
    if channel == "beta":
        has_update = _beta_has_update(local_info["current_commit"], release_data)
    else:
        latest_tag = release_data.get("tag_name") or ""
        has_update = _parse_version(latest_tag) > _parse_version(local_info["current_version"])
    if not has_update:
        return

    target_tag = release_data.get("tag_name") or None
    profile = get_deployment_profile()
    asset = _resolve_asset(profile, release_data)
    log_activity(db, "update_apply", f"Mise à jour planifiée déclenchée (cible : {target_tag or 'branche courante'})")
    await run_update_pipeline(target_tag, asset["download_url"], asset["asset_digest"], "scheduled")

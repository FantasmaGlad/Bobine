"""Routes de mise à jour : recherche, statut, application, boutique Android."""
import asyncio
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.contract import GITHUB_REPO
from app.database import get_db
from app.utils import tor_proxy
from app.utils.activity_log import log_activity
from app.utils.deployment import (
    UpdateUnsupported,
    get_deployment_profile,
    get_profile_handler,
)
from app.updates.orchestrator import (
    acknowledge_current,
    get_status,
    is_running,
    report_external_event,
    run_update_pipeline,
)
from app import release_channel
from app.updates.android import ANDROID_DOWNGRADE_MESSAGE, refuse_android_downgrade
from app.updates.assets import resolve_asset
from app.updates.github import LOOKUP_ERROR_MESSAGES, fetch_release_for_channel
from app.updates.local_build import get_local_version_info, get_update_channel
from app.updates.versions import evaluate_update


router = APIRouter(prefix="/api/updates", tags=["updates"])


class AndroidUpdateCallback(BaseModel):
    """Rappel émis par `UpdateManager.kt` pendant (progression) puis à la fin
    du téléchargement de l'APK (succès ou échec) — `apply_update()` du profil Android
    (backend/app/utils/deployment_profiles/android.py) délègue le
    téléchargement à un thread Kotlin asynchrone et ne peut donc pas
    connaître l'issue réelle avant que ce rappel n'arrive."""

    status: str  # "progress", "downloaded" ou "error"
    message: str | None = None
    percent: int | None = None


@router.get("/check")
async def check_updates(refresh: bool = False, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Vérifie la disponibilité d'une nouvelle release officielle sur GitHub,
    en respectant le canal choisi dans Réglages → Mises à jour (Stable,
    Bêta ou Canary). Gère gracieusement le mode hors-ligne sans planter.
    `refresh` contourne la fenêtre anti-doublon (clic explicite sur
    "Rechercher", changement de canal) ; la requête reste conditionnelle
    (ETag).
    """
    # Jusqu'à quatre appels `git` synchrones : hors de la boucle d'évènements.
    local_info = await run_in_threadpool(get_local_version_info)
    now_iso = datetime.now(timezone.utc).isoformat()
    channel = get_update_channel(db)

    profile = get_deployment_profile()
    handler = get_profile_handler()

    if handler.is_store_managed():
        # État de la mise à jour côté Google Play (interrogation hors de la boucle d'évènements, délai borné).
        try:
            store = await asyncio.wait_for(asyncio.to_thread(handler.store_update_status), timeout=25)
        except Exception:
            store = {"state": "unavailable"}
        return {
            "store": {"provider": "google_play", **store},
            "channel": channel,
            "current_version": local_info["current_version"],
            "current_tag": local_info["current_tag"],
            "current_commit": local_info["current_commit"],
            "local_build": local_info["local_rolling_channel"] or release_channel.DEFAULT_CHANNEL,
            "deployment_profile": profile,
            "checked_at": now_iso,
            "store_managed": True,
            "online": True,
            "error_code": None,
            "latest_version": None,
            "has_update": False,
            "is_downgrade": False,
            "release_title": None,
            "release_notes": None,
            "published_at": None,
            "html_url": None,
            "can_auto_apply": False,
            "download_url": None,
            "asset_name": None,
            "asset_size": None,
        }

    release_data, error_code = await fetch_release_for_channel(channel, force=refresh)

    base = {
        "channel": channel,
        "current_version": local_info["current_version"],
        "current_tag": local_info["current_tag"],
        "current_commit": local_info["current_commit"],
        "local_build": local_info["local_rolling_channel"] or release_channel.DEFAULT_CHANNEL,
        "deployment_profile": profile,
        "checked_at": now_iso,
    }

    if not release_data:
        return {
            **base,
            "online": False,
            "error_code": error_code or "offline",
            "latest_version": None,
            "has_update": False,
            "is_downgrade": False,
            "release_title": None,
            "release_notes": None,
            "published_at": None,
            "html_url": None,
            "can_auto_apply": handler.can_auto_apply(),
            "download_url": None,
            "asset_name": None,
            "asset_size": None,
            "message": LOOKUP_ERROR_MESSAGES.get(error_code or "offline", LOOKUP_ERROR_MESSAGES["offline"]),
        }

    latest_tag = release_data.get("tag_name") or ""
    html_url = release_data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"
    evaluation = await refuse_android_downgrade(
        profile, local_info, release_data, evaluate_update(channel, local_info, release_data)
    )

    asset = resolve_asset(profile, release_data, handler.asset_variant())
    # Profil sans checkout git : sans asset (ni empreinte) pour CE profil
    # dans la release, il n'y a rien à installer automatiquement — l'interface
    # bascule alors sur le lien de téléchargement manuel plutôt que de
    # proposer un bouton "Mettre à jour" voué à l'échec.
    can_auto_apply = handler.can_auto_apply()
    if can_auto_apply and not handler.supports_git_versioning() and not (
        asset["download_url"] and asset["asset_digest"]
    ):
        can_auto_apply = False

    return {
        **base,
        "online": True,
        "error_code": error_code,
        "latest_version": evaluation["latest_version"],
        "has_update": evaluation["has_update"],
        "is_downgrade": evaluation["is_downgrade"],
        "release_title": release_data.get("name") or latest_tag,
        "release_notes": release_data.get("body") or "",
        "published_at": release_data.get("published_at") or "",
        "html_url": html_url,
        "can_auto_apply": can_auto_apply,
        "download_url": asset["download_url"] or html_url,
        "asset_name": asset["asset_name"],
        "asset_size": asset["asset_size"],
        **({"message": ANDROID_DOWNGRADE_MESSAGE} if evaluation.get("downgrade_blocked") else {}),
    }


class TorCheckRequest(BaseModel):
    # Adresse à essayer avant de l'enregistrer ; absente : le réglage en vigueur.
    proxy: str | None = Field(default=None, max_length=80)


@router.post("/tor-check")
async def tor_check(payload: TorCheckRequest) -> dict[str, Any]:
    """Vérifie par le service de contrôle de Tor que les mises à jour sortiraient bien par Tor. `source` :
    `existing` (proxy déjà ouvert) ou `on_demand` (Tor lancé par Bobine, arrêté après quelques minutes)."""
    proxy = payload.proxy
    if proxy is not None:
        try:
            tor_proxy.parse_proxy(proxy)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await asyncio.to_thread(tor_proxy.check, proxy)


@router.get("/status")
async def get_update_status() -> dict[str, Any]:
    """État courant (ou dernier connu) du pipeline de mise à jour — lu par
    le frontend au chargement de la page ET par l'overlay de progression
    en repli si le WebSocket n'est pas connecté au moment où une mise à
    jour planifiée se termine (cas concret : déclenchement à 3h du matin,
    personne devant l'écran)."""
    return get_status()


@router.post("/acknowledge")
async def acknowledge_update() -> dict[str, Any]:
    """Acquitte le cycle de mise à jour courant (bannière/notification
    fermée manuellement par l'utilisateur) — persisté côté serveur pour que
    l'acquittement survive à un rechargement de page ou à un redémarrage de
    service déclenché par la mise à jour elle-même, au lieu de réapparaître
    en boucle (cf. `updates.orchestrator.acknowledge_current`)."""
    return await acknowledge_current()


@router.post("/_android-callback")
async def android_update_callback(payload: AndroidUpdateCallback) -> dict[str, str]:
    """Rappel interne (boucle locale uniquement, jamais exposé au delà de
    127.0.0.1 par la configuration réseau du profil Android) : `UpdateManager.
    kt` l'appelle pendant puis à la fin du téléchargement de l'APK, puisque
    `apply_update()` côté Python ne peut pas connaître cette issue avant
    que le thread Kotlin ne l'ait déterminée."""
    if payload.status == "progress":
        await report_external_event("downloading", message=payload.message, percent=payload.percent)
    elif payload.status == "downloaded":
        await report_external_event(
            "awaiting_user_confirmation",
            message=payload.message or "APK téléchargé — confirmez l'installation sur l'appareil.",
        )
    else:
        await report_external_event("failed", message=payload.message, error=payload.message)
    return {"status": "ok"}


async def _store_action(action: str) -> dict[str, Any]:
    handler = get_profile_handler()
    if not handler.is_store_managed():
        raise HTTPException(status_code=400, detail="Cette installation ne vient pas d'une boutique.")
    try:
        result = await asyncio.wait_for(asyncio.to_thread(getattr(handler, action)), timeout=30)
    except UpdateUnsupported as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Google Play n'a pas répondu à temps.") from exc
    return {"ok": True, **{k: v for k, v in result.items() if k != "ok"}}


@router.post("/store/start")
async def store_start() -> dict[str, Any]:
    """Build Google Play : lance la mise à jour par Google Play (téléchargement en arrière-plan)."""
    return await _store_action("store_update_start")


@router.post("/store/complete")
async def store_complete() -> dict[str, Any]:
    """Build Google Play : installe la mise à jour téléchargée (l'application redémarre)."""
    return await _store_action("store_update_complete")


@router.post("/store/open")
async def store_open() -> dict[str, Any]:
    """Build Google Play : ouvre la fiche de l'application dans Google Play."""
    return await _store_action("store_open_listing")


@router.post("/apply")
async def apply_update(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> dict[str, str]:
    """Déclenche la mise à jour du système en tâche de fond.

    Vérifie si le profil de déploiement supporte l'application automatique
    et qu'aucune mise à jour n'est déjà en cours (409 sinon — corrige le
    risque de deux installations concurrentes sur un double clic ou deux
    onglets ouverts)."""
    handler = get_profile_handler()
    if handler.is_store_managed():
        raise HTTPException(
            status_code=400,
            detail="Cette application est installée depuis une boutique : ses mises à jour passent par la boutique.",
        )
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
    # le canal Stable/Bêta/Canary courant, y compris si l'utilisateur l'a
    # changé entre le dernier "Rechercher une mise à jour" et ce clic.
    # `force=True` : jamais sur une réponse en cache vieille de plusieurs
    # minutes.
    channel = get_update_channel(db)
    release_data, error_code = await fetch_release_for_channel(channel, force=True)
    if not release_data:
        raise HTTPException(
            status_code=503,
            detail=LOOKUP_ERROR_MESSAGES.get(error_code or "offline", LOOKUP_ERROR_MESSAGES["offline"]),
        )
    # Un retour en arrière (is_downgrade) est accepté ICI — c'est l'action
    # explicite du bouton — mais pas un clic sur une version déjà installée.
    # Jusqu'à quatre appels `git` synchrones : hors de la boucle d'évènements.
    local_info = await run_in_threadpool(get_local_version_info)
    profile = get_deployment_profile()
    evaluation = await refuse_android_downgrade(
        profile, local_info, release_data, evaluate_update(channel, local_info, release_data)
    )
    if evaluation.get("downgrade_blocked"):
        raise HTTPException(status_code=400, detail=ANDROID_DOWNGRADE_MESSAGE)
    if not evaluation["has_update"]:
        raise HTTPException(status_code=400, detail="Aucune mise à jour à appliquer : la version installée est déjà la bonne.")

    target_tag = release_data.get("tag_name") or None
    asset = resolve_asset(profile, release_data, handler.asset_variant())
    if not handler.supports_git_versioning():
        if not asset["download_url"]:
            raise HTTPException(
                status_code=400,
                detail=f"La release {target_tag or ''} ne contient aucun paquet pour ce profil ({profile}) — téléchargement manuel requis.",
            )
        if not asset["asset_digest"]:
            raise HTTPException(
                status_code=400,
                detail="Empreinte SHA-256 indisponible pour le paquet de cette release — installation automatique refusée par précaution.",
            )

    log_activity(db, "update_apply", f"Mise à jour manuelle déclenchée (cible : {target_tag or 'branche courante'})")
    background_tasks.add_task(
        run_update_pipeline, target_tag, asset["download_url"], asset["asset_digest"], "manual"
    )
    return {
        "status": "started",
        "message": "Téléchargement et application de la mise à jour en cours...",
    }

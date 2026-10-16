import asyncio
import json
import logging
import re
import subprocess
import time
import urllib.error
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
    acknowledge_current,
    get_status,
    is_running,
    report_external_event,
    run_update_pipeline,
)
from app.utils.version import get_app_commit, get_app_tag, get_app_version, is_prerelease_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/updates", tags=["updates"])

GITHUB_REPO = "FantasmaGlad/Bobine"
# "stable" n'interroge QUE /releases/latest, qui exclut structurellement les
# pre-releases et brouillons côté API GitHub — aucun risque qu'un canal
# stable voie jamais une bêta, même en cas de bug côté filtrage applicatif.
# "beta" interroge un tag FIXE ("beta") — un seul fichier de release Bêta
# sur GitHub, republié en place à chaque build plutôt qu'un nouveau tag par
# itération. Voir .github/workflows/ci.yml, job
# `release-beta` : force-déplace ce tag et republie dessus à chaque
# déclenchement manuel.
_RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_RELEASES_BETA_TAG_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/beta"
_COMMITS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits"
_VALID_CHANNELS = ("stable", "beta")
_STABLE_TAG_RE = re.compile(r"^V\d+\.\d+\.\d+$")
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")

# Messages affichés dans Réglages par code d'erreur de recherche — la
# distinction compte : "hors ligne" pour une simple limite de débit GitHub
# (60 requêtes/h/IP sans jeton, vite atteinte derrière le NAT d'une salle de
# sport) faisait chercher un problème Wi-Fi inexistant.
_LOOKUP_ERROR_MESSAGES = {
    "offline": "Impossible de contacter les serveurs de mise à jour (hors ligne ou indisponible).",
    "rate_limited": "GitHub limite temporairement les vérifications depuis ce réseau — réessayez dans quelques minutes.",
    "not_found_beta": "Aucune version Bêta n'est publiée pour le moment — réessayez dans quelques minutes.",
    "not_found_stable": "Aucune version stable n'est publiée pour le moment.",
}

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
    """Rappel émis par `UpdateManager.kt` pendant (progression) puis à la fin
    du téléchargement de l'APK (succès ou échec) — `apply_update()` du profil Android
    (backend/app/utils/deployment_profiles/android.py) délègue le
    téléchargement à un thread Kotlin asynchrone et ne peut donc pas
    connaître l'issue réelle avant que ce rappel n'arrive."""

    status: str  # "progress", "downloaded" ou "error"
    message: str | None = None
    percent: int | None = None


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
    inférieure aux alphanumériques, comme le veut semver)."""
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


def _git_lines(args: list[str], repo_dir: Path) -> list[str]:
    """Sortie ligne par ligne d'une commande git en lecture seule, liste vide
    en cas d'échec — jamais d'exception : ce code sert à de l'AFFICHAGE."""
    try:
        res = subprocess.run(
            ["git", *args], cwd=repo_dir, capture_output=True, text=True, timeout=3, check=True,
        )
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _get_local_version_info() -> dict[str, Any]:
    """Détermine la version, le commit et la NATURE (stable/bêta) du build local.

    N'exécute `git` que sur les profils dont le dossier d'installation est
    un vrai checkout (aujourd'hui : l'appliance headless seule) — un paquet
    figé (`.exe`, `.app`, `.deb`) n'a pas de `.git` et ces appels
    échoueraient systématiquement en pure perte.

    `is_prerelease_build` distingue un build du canal Bêta d'une Stable de
    même numéro de base : sans ça, un utilisateur Bêta qui repasse sur le
    canal Stable ne se voyait JAMAIS proposer la Stable (même base, ou base
    inférieure), contrairement à la promesse affichée dans Réglages."""
    commit = get_app_commit()
    tag = get_app_tag()
    prerelease = is_prerelease_version(get_app_version())

    if not get_profile_handler().supports_git_versioning():
        return {
            "current_version": tag, "current_tag": tag, "current_commit": commit,
            "is_prerelease_build": prerelease,
        }

    repo_dir = Path(__file__).resolve().parent.parent.parent
    head = _git_lines(["rev-parse", "--short", "HEAD"], repo_dir)
    if head:
        commit = head[0]

    # Tags posés EXACTEMENT sur le commit courant : seule source fiable pour
    # savoir si ce checkout EST une Stable (tag strict Vx.y.z) ou la Bêta
    # (tag mobile "beta") — `git describe` seul tranche arbitrairement
    # quand les deux tags pointent le même commit (cas courant juste après
    # la promotion d'une Bêta en Stable).
    tags_here = _git_lines(["tag", "--points-at", "HEAD"], repo_dir)
    stable_here = sorted((t for t in tags_here if _STABLE_TAG_RE.match(t)), key=_parse_version)
    if stable_here:
        version = stable_here[-1]
        return {
            "current_version": version, "current_tag": version, "current_commit": commit,
            "is_prerelease_build": False,
        }
    if "beta" in tags_here:
        base = get_app_version().lstrip("vV")
        version = f"V{base}" if "-" in base else f"V{base}-beta"
        return {
            "current_version": version, "current_tag": "beta", "current_commit": commit,
            "is_prerelease_build": True,
        }

    described = _git_lines(["describe", "--tags", "--always"], repo_dir)
    if described:
        tag = described[0]

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
        "is_prerelease_build": False,
    }


# --- Recherche de la release sur GitHub -----------------------------------

# Cache par canal : dernière réponse valide + son ETag. Une requête
# conditionnelle (If-None-Match) qui renvoie 304 NE COMPTE PAS dans la limite
# de débit GitHub — on peut donc revalider à chaque ouverture de Réglages
# sans épuiser le quota partagé du réseau. En cas d'échec (hors ligne, limite
# atteinte, republication de la Bêta en cours — la CI supprime puis recrée la
# release, d'où une courte fenêtre en 404), la dernière réponse connue est
# resservie au lieu d'afficher "hors ligne".
_RELEASE_CACHE: dict[str, dict[str, Any]] = {}
_DEDUPE_WINDOW_SECONDS = 10.0
_GITHUB_TIMEOUT_SECONDS = 6.0


def _github_get(url: str, etag: str | None = None) -> tuple[int, dict[str, Any] | None, str | None]:
    """GET JSON synchrone vers l'API GitHub. Renvoie (statut, JSON, ETag) ;
    statut 304 -> JSON None (le cache reste valable). Lève `urllib.error.
    URLError` pour toute défaillance réseau, `HTTPError` pour les statuts
    d'erreur — classés par l'appelant."""
    headers = {
        "User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)",
        "Accept": "application/vnd.github+json",
    }
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=_GITHUB_TIMEOUT_SECONDS) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        raise


def _classify_http_error(channel: str, e: urllib.error.HTTPError) -> str:
    if e.code in (403, 429):
        return "rate_limited"
    if e.code == 404:
        return f"not_found_{channel}"
    return "offline"


def _lookup_release_blocking(channel: str, force: bool) -> tuple[dict[str, Any] | None, str | None]:
    cached = _RELEASE_CACHE.get(channel)
    now = time.monotonic()
    if cached and not force and now - cached["checked_at"] < _DEDUPE_WINDOW_SECONDS:
        return cached["data"], None

    url = _RELEASES_BETA_TAG_URL if channel == "beta" else _RELEASES_LATEST_URL
    try:
        status, data, etag = _github_get(url, cached["etag"] if cached else None)
    except urllib.error.HTTPError as e:
        code = _classify_http_error(channel, e)
        logger.info(f"Vérification GitHub refusée (HTTP {e.code}, canal {channel}) : {code}")
        return (cached["data"] if cached else None), code
    except Exception as e:
        logger.info(f"Vérification GitHub indisponible (hors-ligne ou délai dépassé) : {e}")
        return (cached["data"] if cached else None), "offline"

    if status == 304 and cached:
        cached["checked_at"] = now
        return cached["data"], None
    if not isinstance(data, dict):
        return (cached["data"] if cached else None), "offline"

    if channel == "beta" and not _SHA_RE.match((data.get("target_commitish") or "").lower()):
        # `target_commitish` peut valoir un nom de branche si la release a été
        # créée à la main sans `--target <sha>` : la comparaison de commits
        # déclarerait alors une mise à jour À CHAQUE vérification. On résout
        # le commit réel derrière le tag fixe "beta".
        try:
            _, commit_data, _ = _github_get(f"{_COMMITS_URL}/beta")
            sha = (commit_data or {}).get("sha")
            if sha:
                data["target_commitish"] = sha
        except Exception as e:
            logger.info(f"Résolution du commit du tag beta impossible : {e}")

    _RELEASE_CACHE[channel] = {"data": data, "etag": etag, "checked_at": now}
    return data, None


async def _fetch_release_for_channel(
    channel: str, force: bool = False
) -> tuple[dict[str, Any] | None, str | None]:
    """Interroge GitHub pour le canal donné — partagé entre `check_updates()`
    (affichage), `apply_update()` (résolution du tag cible) et la
    planification, pour ne jamais risquer que ces chemins déterminent une
    release différente. Renvoie (release, code_erreur) : une release
    ANCIENNE (cache) peut accompagner un code d'erreur, l'appelant décide
    s'il s'en contente (affichage) ou non (application : `force=True`)."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _lookup_release_blocking, channel, force)


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


def _evaluate_update(channel: str, local: dict[str, Any], release_data: dict[str, Any]) -> dict[str, Any]:
    """Décision pure (aucun I/O, testable) : y a-t-il quelque chose à
    installer pour ce canal, et est-ce un retour en arrière ?

    Canal Stable : une version strictement plus récente est toujours
    proposée. Si le build local est un build BÊTA, la Stable la plus récente
    est proposée même quand elle est numériquement INFÉRIEURE (`is_downgrade`)
    — c'est le geste "repasser en Stable à tout moment" promis dans
    Réglages. Jamais appliquée automatiquement par la planification
    (`run_scheduled_update_if_available`) : un retour en arrière reste
    toujours un clic explicite.

    Canal Bêta : comparaison de commits (cf. `_beta_has_update`)."""
    if channel == "beta":
        remote_short = _short(release_data.get("target_commitish"))
        return {
            "has_update": _beta_has_update(local["current_commit"], release_data),
            "is_downgrade": False,
            "latest_version": f"beta ({remote_short})" if remote_short else "beta",
        }
    latest_tag = release_data.get("tag_name") or ""
    latest, current = _parse_version(latest_tag), _parse_version(local["current_version"])
    if latest > current:
        return {"has_update": True, "is_downgrade": False, "latest_version": latest_tag}
    if local.get("is_prerelease_build") and latest != current:
        return {"has_update": True, "is_downgrade": True, "latest_version": latest_tag}
    return {"has_update": False, "is_downgrade": False, "latest_version": latest_tag}


def _asset_matches_variant(name: str, variant: str | None) -> bool:
    """Android publie deux APK par release (`Bobine-<v>.apk` pour téléphone/
    tablette, `Bobine-TV-<v>.apk` pour Android TV, `applicationId` différents)
    — `variant` "tv" ne retient que le second, toute autre valeur l'exclut."""
    is_tv = "-tv-" in name or name.startswith("bobine-tv")
    return is_tv if variant == "tv" else not is_tv


def _resolve_asset(
    profile: str, release_data: dict[str, Any] | None, variant: str | None = None
) -> dict[str, Any]:
    """Cherche l'asset adapté au profil de déploiement courant parmi ceux
    d'une release GitHub. Renvoie systématiquement les quatre mêmes clés
    (valant `None` si aucun asset ne correspond), pour que les appelants
    n'aient chacun qu'une seule forme de résultat à gérer. `digest` reprend
    le champ natif que l'API GitHub Releases fournit déjà pour chaque asset
    (`"sha256:<hex>"`) — aucune infrastructure de checksum supplémentaire
    n'est nécessaire pour vérifier l'intégrité d'un téléchargement avant de
    l'exécuter avec des privilèges élevés (cf.
    `update_orchestrator.download_with_progress`). `variant` départage les
    profils qui publient plusieurs assets de même extension (Android TV)."""
    target_ext = _ASSET_EXTENSION_BY_PROFILE.get(profile)
    assets = (release_data or {}).get("assets") or []
    matched = None
    if target_ext:
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if not name.endswith(target_ext):
                continue
            if profile == "android" and not _asset_matches_variant(name, variant):
                continue
            matched = asset
            break
    return {
        "download_url": matched.get("browser_download_url") if matched else None,
        "asset_name": matched.get("name") if matched else None,
        "asset_size": matched.get("size") if matched else None,
        "asset_digest": matched.get("digest") if matched else None,
    }


@router.get("/check")
async def check_updates(refresh: bool = False, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Vérifie la disponibilité d'une nouvelle release officielle sur GitHub,
    en respectant le canal choisi dans Réglages → Mises à jour (Stable ou
    Bêta). Gère gracieusement le mode hors-ligne sans planter. `refresh`
    contourne la fenêtre anti-doublon (clic explicite sur "Rechercher",
    changement de canal) ; la requête reste conditionnelle (ETag).
    """
    local_info = _get_local_version_info()
    now_iso = datetime.now(timezone.utc).isoformat()
    channel = _get_update_channel(db)

    release_data, error_code = await _fetch_release_for_channel(channel, force=refresh)

    profile = get_deployment_profile()
    handler = get_profile_handler()

    base = {
        "channel": channel,
        "current_version": local_info["current_version"],
        "current_tag": local_info["current_tag"],
        "current_commit": local_info["current_commit"],
        "local_build": "beta" if local_info["is_prerelease_build"] else "stable",
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
            "message": _LOOKUP_ERROR_MESSAGES.get(error_code or "offline", _LOOKUP_ERROR_MESSAGES["offline"]),
        }

    latest_tag = release_data.get("tag_name") or ""
    html_url = release_data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases"
    evaluation = _evaluate_update(channel, local_info, release_data)

    asset = _resolve_asset(profile, release_data, handler.asset_variant())
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
    }


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
    en boucle (cf. `update_orchestrator.acknowledge_current`)."""
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
    # entre le dernier "Rechercher une mise à jour" et ce clic. `force=True`
    # : jamais sur une réponse en cache vieille de plusieurs minutes.
    channel = _get_update_channel(db)
    release_data, error_code = await _fetch_release_for_channel(channel, force=True)
    if not release_data:
        raise HTTPException(
            status_code=503,
            detail=_LOOKUP_ERROR_MESSAGES.get(error_code or "offline", _LOOKUP_ERROR_MESSAGES["offline"]),
        )
    # Un retour en arrière (is_downgrade) est accepté ICI — c'est l'action
    # explicite du bouton — mais pas un clic sur une version déjà installée.
    evaluation = _evaluate_update(channel, _get_local_version_info(), release_data)
    if not evaluation["has_update"]:
        raise HTTPException(status_code=400, detail="Aucune mise à jour à appliquer : la version installée est déjà la bonne.")

    target_tag = release_data.get("tag_name") or None
    profile = get_deployment_profile()
    asset = _resolve_asset(profile, release_data, handler.asset_variant())
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


async def run_scheduled_update_if_available(db: Session) -> None:
    """Appelée par `scheduler_manager` au créneau planifié (Réglages → Mise
    à jour automatique). Vérifie d'abord qu'une mise à jour existe RÉELLEMENT
    avant de déclencher quoi que ce soit — contrairement au bouton manuel,
    personne ne clique ici, donc pas de retour utilisateur immédiat en cas
    de "rien à faire" à gérer, juste un silence normal dans les journaux.
    Un retour en arrière (Bêta -> Stable plus ancienne) n'est JAMAIS
    déclenché sans clic : la planification n'installe que des mises à jour
    montantes."""
    handler = get_profile_handler()
    if not handler.can_schedule_auto_apply() or is_running():
        return
    channel = _get_update_channel(db)
    release_data, _ = await _fetch_release_for_channel(channel, force=True)
    if not release_data:
        return
    evaluation = _evaluate_update(channel, _get_local_version_info(), release_data)
    if not evaluation["has_update"] or evaluation["is_downgrade"]:
        return

    target_tag = release_data.get("tag_name") or None
    profile = get_deployment_profile()
    asset = _resolve_asset(profile, release_data, handler.asset_variant())
    if not handler.supports_git_versioning() and not (asset["download_url"] and asset["asset_digest"]):
        logger.warning("Mise à jour planifiée ignorée : paquet ou empreinte introuvable pour ce profil dans la release.")
        return
    log_activity(db, "update_apply", f"Mise à jour planifiée déclenchée (cible : {target_tag or 'branche courante'})")
    await run_update_pipeline(target_tag, asset["download_url"], asset["asset_digest"], "scheduled")

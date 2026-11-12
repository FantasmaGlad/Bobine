"""Recherche des releases sur GitHub, avec cache conditionnel (ETag) et passage éventuel par Tor."""
import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any
from app.api.contract import GITHUB_REPO
from app.utils import tor_proxy
from app import release_channel
from app.updates.versions import SHA_RE


logger = logging.getLogger(__name__)


RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


COMMITS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits"


COMPARE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/compare"


ROLLING_RELEASE_URLS = {
    channel.id: f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{channel.release_tag}"
    for channel in release_channel.CHANNELS
    if channel.rolling
}


LOOKUP_ERROR_MESSAGES = {
    "offline": "Impossible de contacter les serveurs de mise à jour (hors ligne ou indisponible).",
    "rate_limited": "GitHub limite temporairement les vérifications depuis ce réseau — réessayez dans quelques minutes.",
    "not_found_beta": "Aucune version Bêta n'est publiée pour le moment — réessayez dans quelques minutes.",
    "not_found_canary": "Aucune version Canary n'est publiée pour le moment — réessayez dans quelques minutes.",
    "not_found_stable": "Aucune version stable n'est publiée pour le moment.",
}


RELEASE_CACHE: dict[str, dict[str, Any]] = {}


DEDUPE_WINDOW_SECONDS = 10.0


TOR_DEDUPE_WINDOW_SECONDS = 3600.0


GITHUB_TIMEOUT_SECONDS = 6.0


def github_get(url: str, etag: str | None = None) -> tuple[int, dict[str, Any] | None, str | None]:
    """GET JSON synchrone vers l'API GitHub."""
    headers = {
        "User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)",
        "Accept": "application/vnd.github+json",
    }
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        with tor_proxy.urlopen(req, timeout=tor_proxy.request_timeout(GITHUB_TIMEOUT_SECONDS)) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        raise


def classify_http_error(channel: str, e: urllib.error.HTTPError) -> str:
    if e.code in (403, 429):
        return "rate_limited"
    if e.code == 404:
        return f"not_found_{channel}"
    return "offline"


def lookup_release_blocking(channel: str, force: bool) -> tuple[dict[str, Any] | None, str | None]:
    cached = RELEASE_CACHE.get(channel)
    now = time.monotonic()
    window = TOR_DEDUPE_WINDOW_SECONDS if tor_proxy.is_enabled() else DEDUPE_WINDOW_SECONDS
    if cached and not force and now - cached["checked_at"] < window:
        return cached["data"], None

    url = ROLLING_RELEASE_URLS.get(channel, RELEASES_LATEST_URL)
    try:
        status, data, etag = github_get(url, cached["etag"] if cached else None)
    except urllib.error.HTTPError as e:
        code = classify_http_error(channel, e)
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

    if channel in ROLLING_RELEASE_URLS:
        data["target_commitish"] = ""
        try:
            _, commit_data, _ = github_get(f"{COMMITS_URL}/{channel}")
            sha = str((commit_data or {}).get("sha") or "").lower()
            if SHA_RE.match(sha):
                data["target_commitish"] = sha
        except Exception as e:
            logger.info(f"Résolution du commit du tag {channel} impossible : {e}")

    RELEASE_CACHE[channel] = {"data": data, "etag": etag, "checked_at": now}
    return data, None


async def fetch_release_for_channel(
    channel: str, force: bool = False
) -> tuple[dict[str, Any] | None, str | None]:
    """Interroge GitHub pour le canal donné — partagé entre `check_updates()`."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lookup_release_blocking, channel, force)


COMMIT_DISTANCE_CACHE: dict[tuple[str, str], int] = {}


def commit_distance_blocking(local_commit: str, ref: str) -> int | None:
    """Écart signé en commits entre la cible `ref` et le build local (`ahead_by - behind_by` de l'API de comparaison GitHub), `None` si inconnu."""
    key = (local_commit, ref)
    if key in COMMIT_DISTANCE_CACHE:
        return COMMIT_DISTANCE_CACHE[key]
    try:
        _, data, _ = github_get(f"{COMPARE_URL}/{local_commit}...{ref}")
        ahead, behind = (data or {}).get("ahead_by"), (data or {}).get("behind_by")
        if not isinstance(ahead, int) or not isinstance(behind, int):
            return None
    except Exception as e:
        logger.info(f"Comparaison de commits {local_commit}...{ref} indisponible : {e}")
        return None
    COMMIT_DISTANCE_CACHE[key] = ahead - behind
    return ahead - behind

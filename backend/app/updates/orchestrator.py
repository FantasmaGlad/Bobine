"""Machine à états de la mise à jour système."""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from app.utils import tor_proxy
from app.utils.deployment import UpdateUnsupported, get_profile_handler
from app.utils.version import get_build_fingerprint
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

DOWNLOAD_CHUNK_SIZE = 64 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30
DOWNLOAD_ATTEMPTS = 3

_lock = asyncio.Lock()

_state: dict[str, Any] = {
    "step": "idle",
    "percent": None,
    "message": None,
    "target_version": None,
    "triggered_by": None,
    "started_at": None,
    "updated_at": None,
    "error": None,
    "acknowledged_started_at": None,
    "from_fingerprint": None,
}

_INTERNAL_KEYS = ("from_fingerprint",)


def _public_state() -> dict[str, Any]:
    return {k: v for k, v in _state.items() if k not in _INTERNAL_KEYS}


def is_running() -> bool:
    """Utilisé par `POST /api/updates/apply` pour répondre 409 plutôt que de lancer un deuxième pipeline concurrent."""
    return _lock.locked()


def get_status() -> dict[str, Any]:
    """État courant (ou dernier connu) — copie défensive, jamais l'objet interne muté par le pipeline."""
    return _public_state()


def status_file_path() -> Path:
    """Chemin public — utilisé aussi par les handlers dont l'installeur s'exécute dans un script détaché SURVIVANT à la sortie de ce process."""
    from app.config import settings as runtime_settings
    return Path(runtime_settings.logs_dir) / "update_status.json"


def _status_file_path() -> Path:
    return status_file_path()


def _persist_state() -> None:
    try:
        path = _status_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_state), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Échec de persistance de l'état de mise à jour : {e}")


def load_persisted_state_at_startup() -> None:
    """Recharge le dernier état connu au démarrage du process."""
    try:
        path = _status_file_path()
        if not path.exists():
            return
        persisted = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(persisted, dict):
            return
        _state.update(persisted)
        if _state.get("step") in ("done", "failed", "idle"):
            return
        previous = _state.get("from_fingerprint")
        applied = bool(previous) and previous != get_build_fingerprint()
        if applied:
            _state.update(
                step="done", percent=100, error=None,
                message="Mise à jour terminée avec succès.",
            )
        elif _state.get("step") == "awaiting_user_confirmation":
            _state.update(step="idle", percent=None, message=None, error=None)
        else:
            _state.update(
                step="failed",
                error="Le service s'est arrêté avant la fin de la mise à jour — "
                      "la version installée n'a pas changé.",
            )
            _state["message"] = _state["error"]
        _persist_state()
    except Exception as e:
        logger.debug(f"Échec de relecture de l'état de mise à jour persisté : {e}")


async def report_external_event(
    step: str,
    message: str | None = None,
    error: str | None = None,
    percent: int | None = None,
) -> None:
    """Point d'entrée public pour un évènement qui n'arrive PAS depuis `run_update_pipeline` lui-même — aujourd'hui uniquement le rappel Android."""
    await _set_state(step=step, message=message, error=error, percent=percent)


async def acknowledge_current() -> dict[str, Any]:
    """Marque le cycle de mise à jour COURANT (`started_at`) comme vu par l'utilisateur — appelé par `POST /api/updates/acknowledge` quand la notification/bannière est fermée manuellement."""
    _state["acknowledged_started_at"] = _state.get("started_at")
    try:
        await ws_manager.broadcast({"event": "update_progress", **_public_state()})
    except Exception as e:
        logger.warning(f"Échec de diffusion de l'acquittement de mise à jour : {e}")
    _persist_state()
    return _public_state()


async def _set_state(**kwargs: Any) -> None:
    _state.update(kwargs)
    _state["updated_at"] = time.time()
    try:
        await ws_manager.broadcast({"event": "update_progress", **_public_state()})
    except Exception as e:
        logger.warning(f"Échec de diffusion de la progression de mise à jour : {e}")
    _persist_state()


def make_reporter(loop: asyncio.AbstractEventLoop) -> Callable[..., None]:
    """Callback SYNCHRONE passé aux handlers de profil (`ProfileHandler."""

    def report(step: str, percent: int | None = None, message: str | None = None) -> None:
        asyncio.run_coroutine_threadsafe(
            _set_state(step=step, percent=percent, message=message), loop
        )

    return report


def clean_subprocess_env() -> dict[str, str]:
    """Environnement assaini pour tout sous-processus invoquant un binaire SYSTÈME externe (systemctl, dpkg, git...) depuis ce process."""
    env = dict(os.environ)
    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "LIBPATH"):
        original = env.pop(f"{name}_ORIG", None)
        if original:
            env[name] = original
        else:
            env.pop(name, None)
    return env


def run_checked(
    cmd: list[str],
    cwd: Path | str | None = None,
    timeout: float = 45.0,
) -> subprocess.CompletedProcess:
    """`subprocess.run` qui échoue BRUYAMMENT (exception avec stdout/ stderr inclus) au lieu de laisser l'appelant oublier de vérifier `returncode`."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        env=clean_subprocess_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Commande échouée ({' '.join(cmd)}, code {result.returncode}) : "
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
    return result


def download_with_progress(
    url: str,
    dest: Path,
    expected_digest: str | None,
    on_progress: Callable[[int], None] | None = None,
    on_verifying: Callable[[], None] | None = None,
) -> None:
    """Téléchargement par blocs, avec délai et vérification d'intégrité."""
    if not expected_digest:
        raise RuntimeError(
            "Empreinte d'intégrité indisponible pour cet asset — "
            "installation annulée par précaution."
        )
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            hasher = _download_once(url, part, on_progress)
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_error = e
            part.unlink(missing_ok=True)
            if isinstance(e, OSError) and getattr(e, "errno", None) == 28:
                raise RuntimeError("Espace disque insuffisant pour télécharger la mise à jour.") from e
            logger.warning(f"Téléchargement interrompu (tentative {attempt}/{DOWNLOAD_ATTEMPTS}) : {e}")
            if attempt < DOWNLOAD_ATTEMPTS:
                time.sleep(2 * attempt)
    else:
        raise RuntimeError(
            f"Téléchargement impossible après {DOWNLOAD_ATTEMPTS} tentatives : {last_error}"
        )

    if on_verifying:
        on_verifying()
    actual = hasher.hexdigest().lower()
    expected = expected_digest.split(":")[-1].lower()
    if actual != expected:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            f"Empreinte SHA-256 invalide pour le fichier téléchargé "
            f"(attendu {expected[:12]}…, obtenu {actual[:12]}…) — "
            f"fichier supprimé, installation annulée par précaution."
        )
    part.replace(dest)
    if on_progress:
        on_progress(100)


def _download_once(url: str, part: Path, on_progress: Callable[[int], None] | None):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)"}
    )
    hasher = hashlib.sha256()
    last_percent = -1
    with tor_proxy.urlopen(req, timeout=tor_proxy.request_timeout(DOWNLOAD_TIMEOUT_SECONDS)) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        if total:
            free = shutil.disk_usage(part.parent).free
            if free < total * 1.2:
                raise RuntimeError(
                    f"Espace disque insuffisant pour la mise à jour "
                    f"({free // 1_048_576} Mo libres, {total // 1_048_576} Mo requis)."
                )
        read = 0
        with open(part, "wb") as f:
            while True:
                chunk = resp.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                hasher.update(chunk)
                read += len(chunk)
                if total and on_progress:
                    percent = min(99, int(read * 100 / total))
                    if percent != last_percent:
                        last_percent = percent
                        on_progress(percent)
        if total and read != total:
            raise ConnectionError(f"Fichier tronqué ({read}/{total} octets reçus).")
    return hasher


async def run_update_pipeline(
    target_tag: str | None,
    download_url: str | None = None,
    asset_digest: str | None = None,
    triggered_by: str = "manual",
) -> None:
    """Applique la mise à jour et redémarre les services, via le handler du profil courant."""
    if _lock.locked():
        logger.warning("Une mise à jour est déjà en cours — nouvelle demande ignorée.")
        return

    async with _lock:
        await _set_state(
            step="checking",
            percent=None,
            message="Préparation de la mise à jour…",
            target_version=target_tag,
            triggered_by=triggered_by,
            started_at=time.time(),
            error=None,
            acknowledged_started_at=None,
            from_fingerprint=get_build_fingerprint(),
        )
        logger.info(
            f"Début du processus de mise à jour système "
            f"(cible : {target_tag or 'branche courante'}, déclenchement : {triggered_by})..."
        )

        await asyncio.sleep(0.5)

        loop = asyncio.get_running_loop()
        report = make_reporter(loop)
        handler = get_profile_handler()
        try:
            await asyncio.to_thread(
                handler.apply_update,
                target_tag=target_tag,
                download_url=download_url,
                asset_digest=asset_digest,
                report=report,
            )
            if not handler.async_completion:
                await _set_state(step="done", percent=100, message="Mise à jour terminée avec succès.")
        except UpdateUnsupported as e:
            logger.warning(f"Mise à jour non applicable sur ce profil : {e.message}")
            await _set_state(step="failed", message=e.message, error=e.message)
        except Exception as e:
            logger.error(f"Erreur lors de l'application de la mise à jour : {e}")
            await _set_state(step="failed", message=str(e), error=str(e))

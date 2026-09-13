"""Machine à états de la mise à jour système.

Centralise ce qui vivait auparavant dans `_run_update_pipeline()`
(`routers/updates.py`) et l'étend pour que chaque étape (vérification,
téléchargement, vérification d'intégrité, installation, redémarrage)
diffuse sa progression en temps réel — au lieu de ne renvoyer un succès
au frontend qu'au moment où le travail est simplement PLANIFIÉ (bug
constaté en audit : le bouton affichait « mise à jour réussie » avant
même que le téléchargement ait commencé, masquant tout échec réel).

Trois canaux de sortie pour cet état, tous alimentés depuis un seul
point (`_set_state`) :
  1. Diffusion WebSocket immédiate (`{"event": "update_progress", ...}`)
     pour un client connecté au moment de la mise à jour.
  2. Persistance sur disque (`data/logs/update_status.json`) pour qu'un
     client qui se reconnecte APRÈS un redémarrage de service (cas normal
     d'une mise à jour) retrouve l'issue réelle au lieu de revenir
     silencieusement à un état neutre.
  3. `GET /api/updates/status` (routers/updates.py) qui lit ce même état
     en mémoire — utilisé par le frontend au chargement de la page.
"""

import asyncio
import hashlib
import json
import logging
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal

from app.utils.deployment import UpdateUnsupported, get_profile_handler
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)

UpdateStep = Literal[
    "idle", "checking", "downloading", "verifying", "installing",
    "restarting", "awaiting_user_confirmation", "done", "failed",
]

DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT_SECONDS = 30

# Un seul pipeline de mise à jour à la fois (corrige le constat "double
# clic ou deux onglets peuvent lancer deux installations en parallèle sur
# le même fichier temporaire"). `asyncio.Lock()` ne se lie plus à une
# boucle particulière à la construction depuis Python 3.10 — l'instancier
# ici, au niveau module, est sûr même avant que la boucle asyncio du
# process ne tourne.
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
}


def is_running() -> bool:
    """Utilisé par `POST /api/updates/apply` pour répondre 409 plutôt que
    de lancer un deuxième pipeline concurrent."""
    return _lock.locked()


def get_status() -> dict[str, Any]:
    """État courant (ou dernier connu) — copie défensive, jamais l'objet
    interne muté par le pipeline."""
    return dict(_state)


def status_file_path() -> Path:
    """Chemin public — utilisé aussi par les handlers dont l'installeur
    s'exécute dans un script détaché SURVIVANT à la sortie de ce process
    (ex. le runner PowerShell Windows) et qui doit donc écrire lui-même
    l'issue finale dans ce même fichier, relu par `load_persisted_state_
    at_startup()` au prochain démarrage du backend."""
    from app.config import settings as runtime_settings
    return Path(runtime_settings.logs_dir) / "update_status.json"


def _status_file_path() -> Path:
    return status_file_path()


def _persist_state() -> None:
    """Best-effort : un échec d'écriture disque ne doit jamais faire
    échouer la mise à jour elle-même, seulement dégrader la capacité du
    frontend à retrouver l'état après une reconnexion tardive."""
    try:
        path = _status_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(_state), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Échec de persistance de l'état de mise à jour : {e}")


def load_persisted_state_at_startup() -> None:
    """Recharge le dernier état connu au démarrage du process (appelé
    depuis `main.py::lifespan`) — sans ça, un redémarrage déclenché par
    une mise à jour réussie ferait réapparaître `GET /api/updates/status`
    à "idle" avant même que le frontend ait pu lire le résultat réel."""
    try:
        path = _status_file_path()
        if path.exists():
            persisted = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(persisted, dict):
                _state.update(persisted)
                # Un pipeline ne peut pas être "en cours" après un
                # redémarrage du process qui l'exécutait — un état
                # intermédiaire orphelin (ex. "downloading" si le process
                # a été tué avant d'écrire "failed") serait trompeur.
                if _state.get("step") not in ("done", "failed", "idle"):
                    _state["step"] = "failed"
                    _state["error"] = "Le service a redémarré avant la fin de la mise à jour."
    except Exception as e:
        logger.debug(f"Échec de relecture de l'état de mise à jour persisté : {e}")


async def report_external_event(step: str, message: str | None = None, error: str | None = None) -> None:
    """Point d'entrée public pour un évènement qui n'arrive PAS depuis
    `run_update_pipeline` lui-même — aujourd'hui uniquement le rappel
    Android (`POST /api/updates/_android-callback`, cf. routers/updates.py) :
    `apply_update()` d'Android ne peut connaître l'issue réelle du
    téléchargement qu'après être retourné (délégué à un thread Kotlin
    asynchrone côté JVM), donc après que le pipeline se soit déjà terminé
    de son point de vue. Aucun verrou à tenir ici : à ce stade
    `run_update_pipeline` a déjà relâché `_lock`."""
    await _set_state(step=step, message=message, error=error)


async def _set_state(**kwargs: Any) -> None:
    _state.update(kwargs)
    _state["updated_at"] = time.time()
    try:
        await ws_manager.broadcast({"event": "update_progress", **_state})
    except Exception as e:
        logger.warning(f"Échec de diffusion de la progression de mise à jour : {e}")
    _persist_state()


def make_reporter(loop: asyncio.AbstractEventLoop) -> Callable[..., None]:
    """Callback SYNCHRONE passé aux handlers de profil (`ProfileHandler.
    apply_update`), qui s'exécutent dans un thread via `asyncio.to_thread`
    (jamais directement sur la boucle asyncio — cf. `run_update_pipeline`).
    Reprogramme la mise à jour d'état réelle (coroutine) sur la boucle
    principale depuis ce thread."""

    def report(step: str, percent: int | None = None, message: str | None = None) -> None:
        asyncio.run_coroutine_threadsafe(
            _set_state(step=step, percent=percent, message=message), loop
        )

    return report


def run_checked(
    cmd: list[str],
    cwd: Path | str | None = None,
    timeout: float = 45.0,
) -> subprocess.CompletedProcess:
    """`subprocess.run` qui échoue BRUYAMMENT (exception avec stdout/
    stderr inclus) au lieu de laisser l'appelant oublier de vérifier
    `returncode` — corrige le constat récurrent "git checkout / systemctl
    restart jamais vérifié avant de continuer, y compris en cas
    d'échec réel"."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
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
) -> None:
    """Téléchargement par blocs, avec timeout explicite (contrairement à
    l'ancien `urllib.request.urlretrieve` utilisé sans timeout sur les
    profils Windows et Linux desktop) et vérification d'intégrité.

    `expected_digest` reprend directement le champ `digest` que l'API
    GitHub Releases renvoie déjà nativement pour chaque asset (format
    `"sha256:<hex>"`) — pas besoin d'infrastructure CI supplémentaire
    (fichier SHA256SUMS séparé) pour vérifier ce qui est sur le point
    d'être installé avec des privilèges élevés.

    Fonction SYNCHRONE et bloquante par conception : les handlers de
    profil qui l'appellent tournent déjà dans un thread dédié via
    `asyncio.to_thread` (cf. `run_update_pipeline`), jamais sur la boucle
    asyncio elle-même."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "Bobine-Updater/2.0 (+https://bobine.fit)"}
    )
    hasher = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_percent = -1
    with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT_SECONDS) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        read = 0
        with open(dest, "wb") as f:
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

    if expected_digest:
        actual = hasher.hexdigest().lower()
        expected = expected_digest.split(":")[-1].lower()
        if actual != expected:
            dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Empreinte SHA-256 invalide pour le fichier téléchargé "
                f"(attendu {expected[:12]}…, obtenu {actual[:12]}…) — "
                f"fichier supprimé, installation annulée par précaution."
            )
    if on_progress:
        on_progress(100)


async def run_update_pipeline(
    target_tag: str | None,
    download_url: str | None = None,
    asset_digest: str | None = None,
    triggered_by: str = "manual",
) -> None:
    """Applique la mise à jour et redémarre les services, via le handler
    du profil courant. `target_tag` épingle le checkout sur le tag résolu
    par le canal courant au moment du déclenchement (manuel ou planifié) —
    None si la résolution GitHub a échoué, auquel cas le handler retombe
    sur son ancien comportement (`git pull --ff-only` sur la branche
    courante). `download_url`/`asset_digest` sont l'URL et l'empreinte
    SHA-256 de l'asset pour les profils non-git. `triggered_by` ("manual"
    ou "scheduled") est uniquement informatif, reporté dans l'état pour
    distinguer les deux origines dans les journaux et l'historique
    affiché côté Réglages."""
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
        )
        logger.info(
            f"Début du processus de mise à jour système "
            f"(cible : {target_tag or 'branche courante'}, déclenchement : {triggered_by})..."
        )

        try:
            await ws_manager.broadcast_force_reload()
        except Exception as e:
            logger.warning(f"Échec broadcast WebSocket lors de la mise à jour : {e}")

        await asyncio.sleep(1.0)

        loop = asyncio.get_running_loop()
        report = make_reporter(loop)
        handler = get_profile_handler()
        try:
            # `asyncio.to_thread` — jamais un appel direct sur la coroutine
            # courante : les handlers font des appels bloquants
            # (subprocess, téléchargement) qui, exécutés directement sur
            # la boucle asyncio, gelaient `/api/health` pendant toute la
            # durée de la mise à jour et pouvaient déclencher un
            # redémarrage forcé du process EN PLEIN transfert/installation
            # (cf. `BobineTray._health_poll_loop`, 3 échecs consécutifs).
            await asyncio.to_thread(
                handler.apply_update,
                target_tag=target_tag,
                download_url=download_url,
                asset_digest=asset_digest,
                report=report,
            )
            if _state["step"] not in ("awaiting_user_confirmation",):
                await _set_state(step="done", percent=100, message="Mise à jour terminée avec succès.")
        except UpdateUnsupported as e:
            logger.warning(f"Mise à jour non applicable sur ce profil : {e.message}")
            await _set_state(step="failed", message=e.message, error=e.message)
        except Exception as e:
            logger.error(f"Erreur lors de l'application de la mise à jour : {e}")
            await _set_state(step="failed", message=str(e), error=str(e))

"""Port d'écoute du backend : résolution unique avec repli dynamique, et
publication du port réellement utilisé.

Le port PRÉFÉRÉ reste `settings.port` (8000 par défaut, `BOBINE_PORT` ou
`config.toml`) : le pare-feu (règle Inno Setup, firewalld), l'annonce mDNS, les
signets et la documentation continuent de parler de 8000, et rien ne change
tant que ce port est libre. Quand il est occupé (autre application, ancienne
instance de Bobine qui s'arrête encore, deuxième session utilisateur sur la
même machine), `resolve_port()` essaie les `FALLBACK_SPAN` ports suivants puis
demande un port libre au système plutôt que de laisser le backend mourir en
boucle de relance.

`BOBINE_PORT_STRICT=1` supprime ce repli : le démarrage échoue avec un message
clair. À utiliser là où le port doit être déterministe — typiquement
l'appliance systemd, où la redirection 80 → 8000 (`bobine-redirect.service`),
le pare-feu et les signets supposent 8000.

Le port réellement utilisé est écrit de façon atomique dans un fichier
d'exécution du dossier de données (`backend-runtime.json` : port, pid), supprimé
à l'arrêt. C'est la source de vérité des autres processus de l'application
(barre d'état du bureau, services Android, scripts) : un fichier dont le pid
n'existe plus est ignoré, donc un arrêt brutal ne laisse pas de port fantôme.
Hors de ces lecteurs, l'API le publie dans `network.port` et le répondeur mDNS
dans l'enregistrement du service.

Le sondage « ce port est-il libre ? » et la liaison effective par uvicorn ne
sont pas atomiques : si un autre processus prend le port entre les deux,
uvicorn échoue, le processus s'arrête et le superviseur (barre d'état,
systemd, `ForegroundService`) relance, ce qui refait la résolution.
"""

import atexit
import json
import logging
import os
import signal
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Port préféré quand rien d'autre n'est configuré. Doit rester égal au défaut de
# `Settings.port` (app/config.py) ; les installeurs, le pare-feu et la
# documentation s'appuient sur cette valeur.
DEFAULT_PORT = 8000
# Nombre de ports consécutifs essayés après le port préféré avant de demander
# un port libre au système.
FALLBACK_SPAN = 10
STRICT_ENV = "BOBINE_PORT_STRICT"
RUNTIME_FILE_NAME = "backend-runtime.json"

_LISTEN_HOST = "0.0.0.0"

_active_port: int | None = None
_cleanup_hooks_installed = False


class PortUnavailableError(RuntimeError):
    """Aucun port d'écoute utilisable (port préféré occupé en mode strict, ou
    le système n'a pas pu en attribuer un)."""


def is_strict() -> bool:
    return os.environ.get(STRICT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def preferred_port() -> int:
    """Port préféré : `settings.port` (`BOBINE_PORT`, `config.toml`), sinon 8000."""
    try:
        from app.config import settings
        return int(settings.port)
    except Exception:
        return DEFAULT_PORT


def _can_bind(port: int, host: str = _LISTEN_HOST) -> bool:
    """Même test de liaison que celui d'uvicorn (asyncio) : SO_REUSEADDR sous
    POSIX seulement. Sous Windows il autoriserait à se lier par-dessus un
    écouteur actif et masquerait l'occupation du port."""
    return _bind_error(port, host) is None


def _bind_error(port: int, host: str = _LISTEN_HOST) -> OSError | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "posix" and sys.platform != "cygwin":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        return None
    except OSError as exc:
        return exc
    finally:
        sock.close()


def _system_assigned_port(host: str = _LISTEN_HOST) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
    except OSError as exc:
        raise PortUnavailableError(
            f"Le système n'a pas pu attribuer de port d'écoute à Bobine : {exc}"
        ) from exc
    finally:
        sock.close()


def resolve_port(preferred: int | None = None, *, strict: bool | None = None) -> int:
    """Port d'écoute à utiliser : le préféré s'il est libre ; sinon les
    `FALLBACK_SPAN` suivants, puis un port attribué par le système. En mode
    strict, lève `PortUnavailableError` si le préféré est occupé."""
    wanted = preferred_port() if preferred is None else int(preferred)
    strict = is_strict() if strict is None else strict

    error = _bind_error(wanted)
    if error is None:
        return wanted
    if strict:
        raise PortUnavailableError(
            f"Le port {wanted} est occupé ou inutilisable ({error}) et le repli est désactivé "
            f"({STRICT_ENV}=1). Libérez ce port ou changez-le avec BOBINE_PORT."
        )
    for candidate in range(wanted + 1, min(wanted + FALLBACK_SPAN, 65535) + 1):
        if _can_bind(candidate):
            return candidate
    return _system_assigned_port()


# --- Fichier d'exécution -------------------------------------------------------

def runtime_dir() -> Path:
    """Dossier du fichier d'exécution : stockage interne de l'application sur
    Android (lu aussi par le code Kotlin), sinon racine des données. C'est une
    fonction du système et de l'environnement seuls, donc identique pour le
    backend et pour la barre d'état."""
    from app.config import DATA_ROOT, _android_internal_root
    return _android_internal_root() or DATA_ROOT


def runtime_file(directory: Path | str | None = None) -> Path:
    return (Path(directory) if directory is not None else runtime_dir()) / RUNTIME_FILE_NAME


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # `os.kill(pid, 0)` termine le processus sous Windows : OpenProcess à la place.
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def write_runtime_file(port: int, preferred: int | None = None, directory: Path | str | None = None) -> Path | None:
    """Écrit (remplacement atomique) le fichier d'exécution. Best-effort : un
    dossier non inscriptible est journalisé, jamais fatal pour le démarrage."""
    preferred = preferred_port() if preferred is None else preferred
    payload = {
        "port": int(port),
        "pid": os.getpid(),
        "preferred": int(preferred),
        "fallback": int(port) != int(preferred),
        "started_at": int(time.time()),
    }
    try:
        target = runtime_file(directory)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".backend-runtime-", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
        return target
    except Exception as exc:
        logger.warning("Fichier d'exécution du port non écrit (%s) : les autres processus utiliseront le port préféré.", exc)
        return None


def clear_runtime_file(directory: Path | str | None = None) -> None:
    """Supprime le fichier d'exécution s'il appartient à ce processus (un autre
    backend ayant démarré entre-temps garde le sien)."""
    try:
        target = runtime_file(directory)
        info = _read_file(target)
        if info is not None and info.get("pid") not in (None, os.getpid()):
            return
        target.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Fichier d'exécution du port non supprimé : %s", exc)


def _read_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    port, pid = data.get("port"), data.get("pid")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
        return None
    if not isinstance(pid, int) or isinstance(pid, bool):
        return None
    return data


def read_runtime(directory: Path | str | None = None, *, require_live: bool = True) -> dict[str, Any] | None:
    """Contenu du fichier d'exécution, ou None s'il manque, est illisible ou
    (par défaut) décrit un processus qui n'existe plus."""
    try:
        info = _read_file(runtime_file(directory))
    except Exception:
        return None
    if info is None:
        return None
    if require_live and not _pid_alive(int(info["pid"])):
        return None
    return info


def read_runtime_port(directory: Path | str | None = None) -> int | None:
    info = read_runtime(directory)
    return int(info["port"]) if info else None


def current_port() -> int:
    """Port à joindre pour parler au backend : celui du fichier d'exécution
    d'un backend vivant, sinon le port préféré (comportement historique quand
    rien n'est encore démarré)."""
    return read_runtime_port() or preferred_port()


# --- Cycle de vie utilisé par les lanceurs --------------------------------------

def active_port() -> int:
    """Port sur lequel CE processus écoute (publié par `acquire_listen_port`),
    sinon le port préféré (tests, `uvicorn app.main:app` lancé à la main)."""
    return _active_port if _active_port is not None else preferred_port()


def _terminate_after_cleanup(signum, _frame) -> None:
    release_port()
    signal.signal(signum, signal.SIG_DFL)
    signal.raise_signal(signum)


def _install_cleanup_hooks() -> None:
    """Supprime le fichier d'exécution aussi quand le processus meurt sur SIGTERM
    (arrêt par systemd ou par le tray). uvicorn termine l'arrêt propre puis
    RE-LÈVE le signal avec le gestionnaire d'avant son installation, ce qui tue
    le processus sans repasser par le `finally` du lanceur : sans ce gestionnaire
    le fichier resterait (ignoré ensuite grâce au pid, mais inutilement). Sans
    effet hors du fil principal (Android lance uvicorn dans un fil : son `finally`
    suffit, et un fichier resté après la mort du processus est ignoré par son pid)."""
    global _cleanup_hooks_installed
    if _cleanup_hooks_installed:
        return
    _cleanup_hooks_installed = True
    atexit.register(release_port)
    if os.name == "posix" and threading.current_thread() is threading.main_thread():
        try:
            signal.signal(signal.SIGTERM, _terminate_after_cleanup)
        except (ValueError, OSError):
            pass


def acquire_listen_port() -> int:
    """À appeler une fois, avant `uvicorn.run` : résout le port, le publie
    (fichier d'exécution, `active_port()`) et signale clairement tout repli.
    Lève `PortUnavailableError` en mode strict."""
    global _active_port
    wanted = preferred_port()
    port = resolve_port(wanted)
    _active_port = port
    if port != wanted:
        logger.warning(
            "Le port %d est occupé : Bobine écoute sur le port de repli %d. Les autres appareils doivent "
            "utiliser http://<adresse>:%d. Si un pare-feu filtre les connexions entrantes, ouvrez ce port "
            "(la règle Windows est liée au programme ; le service firewalld fourni n'ouvre que %d).",
            wanted, port, port, DEFAULT_PORT,
        )
    else:
        logger.info("Bobine écoute sur le port %d.", port)
    write_runtime_file(port, wanted)
    _install_cleanup_hooks()
    return port


def release_port() -> None:
    """À appeler quand uvicorn s'est arrêté : supprime le fichier d'exécution."""
    global _active_port
    _active_port = None
    clear_runtime_file()

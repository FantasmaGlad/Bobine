"""Port d'écoute du backend : résolution unique avec repli dynamique, et publication du port réellement utilisé."""

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

from app.api.contract import DEFAULT_PORT

logger = logging.getLogger(__name__)

FALLBACK_SPAN = 10
STRICT_ENV = "BOBINE_PORT_STRICT"
RUNTIME_FILE_NAME = "backend-runtime.json"

_LISTEN_HOST = "0.0.0.0"

_active_port: int | None = None
_cleanup_hooks_installed = False


class PortUnavailableError(RuntimeError):
    """Aucun port d'écoute utilisable (port préféré occupé en mode strict, ou le système n'a pas pu en attribuer un)."""


def is_strict() -> bool:
    return os.environ.get(STRICT_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def preferred_port() -> int:
    """Port préféré : `settings.port` (`BOBINE_PORT`, `config.toml`), sinon 1903."""
    try:
        from app.config import settings
        return int(settings.port)
    except Exception:
        return DEFAULT_PORT


def _can_bind(port: int, host: str = _LISTEN_HOST) -> bool:
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
    """Port d'écoute à utiliser : le préféré s'il est libre ; sinon les `FALLBACK_SPAN` suivants, puis un port attribué par le système."""
    wanted = preferred_port() if preferred is None else int(preferred)
    strict = is_strict() if strict is None else strict
    if not 1 <= wanted <= 65535:
        raise PortUnavailableError(
            f"Le port d'écoute {wanted} est invalide : indiquez une valeur entre 1 et 65535 "
            f"(BOBINE_PORT ou config.toml)."
        )

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


def runtime_dir() -> Path:
    """Dossier du fichier d'exécution : stockage interne de l'application sur Android (lu aussi par le code Kotlin), sinon racine des données."""
    from app.config import DATA_ROOT, _android_internal_root
    return _android_internal_root() or DATA_ROOT


def runtime_file(directory: Path | str | None = None) -> Path:
    return (Path(directory) if directory is not None else runtime_dir()) / RUNTIME_FILE_NAME


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == 259
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
    """Écrit (remplacement atomique) le fichier d'exécution."""
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
    """Supprime le fichier d'exécution s'il appartient à ce processus (un autre backend ayant démarré entre-temps garde le sien)."""
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
    """Contenu du fichier d'exécution, ou None s'il manque, est illisible ou (par défaut) décrit un processus qui n'existe plus."""
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
    """Port à joindre pour parler au backend : celui du fichier d'exécution d'un backend vivant, sinon le port préféré (comportement historique quand rien n'est encore démarré)."""
    return read_runtime_port() or preferred_port()


def active_port() -> int:
    """Port sur lequel CE processus écoute (publié par `acquire_listen_port`), sinon le port préféré (tests, `uvicorn app.main:app` lancé à la main)."""
    return _active_port if _active_port is not None else preferred_port()


def _terminate_after_cleanup(signum, _frame) -> None:
    release_port()
    signal.signal(signum, signal.SIG_DFL)
    signal.raise_signal(signum)


def _install_cleanup_hooks() -> None:
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
    """À appeler une fois, avant `uvicorn.run` : résout le port, le publie (fichier d'exécution, `active_port()`) et signale clairement tout repli."""
    global _active_port
    wanted = preferred_port()
    port = resolve_port(wanted)
    _active_port = port
    if port != wanted:
        logger.warning(
            "Le port %d est occupé : Bobine écoute sur le port de repli %d. Les autres appareils doivent "
            "utiliser http://<adresse>:%d. Windows : la règle de pare-feu liée au programme couvre ce port. Linux : les "
            "règles posées par les paquets couvrent les ports %d à %d ; hors de cette plage, ouvrez-le à la main.",
            wanted, port, port, DEFAULT_PORT, DEFAULT_PORT + FALLBACK_SPAN,
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

import os

from . import posix, windows


def _platform():
    return windows if os.name == "nt" else posix


def pid_alive(pid: int) -> bool:
    """Vrai si un processus de ce PID existe encore."""
    if pid <= 0:
        return False
    return _platform().pid_alive(pid)


def install_termination_handler(handler) -> None:
    """Appelle `handler` sur SIGTERM là où ce signal existe (POSIX) ; à appeler depuis le fil principal."""
    _platform().install_termination_handler(handler)

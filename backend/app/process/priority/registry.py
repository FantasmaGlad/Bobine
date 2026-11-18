import os

from . import posix, windows
from .policy import shares_machine_with_browser


def _platform():
    return windows if os.name == "nt" else posix


def background_priority_popen_kwargs() -> dict:
    """Arguments de `Popen` qui créent le processus en priorité réduite (Windows)."""
    return _platform().popen_kwargs() if shares_machine_with_browser() else {}


def lower_process_priority(pid: int) -> None:
    """Réduit la priorité d'un processus déjà lancé (`nice 10` sous POSIX)."""
    if shares_machine_with_browser():
        _platform().lower(pid)

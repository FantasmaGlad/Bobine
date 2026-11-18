import os

from . import posix, windows


def _platform():
    return windows if os.name == "nt" else posix


def executable_name(name: str) -> str:
    """Nom du fichier exécutable d'un programme sur cette plateforme."""
    return f"{name}{_platform().SUFFIX}"


def hidden_console_kwargs() -> dict:
    """Arguments de `Popen` qui empêchent l'ouverture d'une console (Windows)."""
    return _platform().hidden_console_kwargs()

import os
import sys

from . import linux, posix, windows


def _platform():
    if os.name == "nt":
        return windows
    return linux if sys.platform.startswith("linux") else posix


def executable_name(name: str) -> str:
    """Nom du fichier exécutable d'un programme sur cette plateforme."""
    return f"{name}{_platform().SUFFIX}"


def hidden_console_kwargs() -> dict:
    """Arguments de `Popen` qui empêchent l'ouverture d'une console (Windows)."""
    return _platform().hidden_console_kwargs()


def tied_to_parent_kwargs() -> dict:
    """Arguments de `Popen` d'un démon qui doit s'arrêter avec Bobine (signal de mort du parent sous Linux)."""
    return _platform().tied_to_parent_kwargs()


def restrict_directory(path) -> None:
    """Réserve un dossier au seul utilisateur courant (POSIX)."""
    _platform().restrict_directory(path)

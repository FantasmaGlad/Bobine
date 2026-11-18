"""Plateformes de la machine pour les sondes, de la plus précise à la plus générale."""
import sys
from types import ModuleType
from typing import Callable, TypeVar

from .probe import is_android_system

T = TypeVar("T")


def detected() -> list[str]:
    found = ["android"] if is_android_system() else []
    if sys.platform.startswith("linux"):
        found.append("linux")
    elif sys.platform == "darwin":
        found.append("macos")
    elif sys.platform == "win32":
        found.append("windows")
    return found


def first_answer(implementations: dict[str, ModuleType], read: Callable[[ModuleType], T]) -> T | None:
    """Première réponse non vide des implémentations des plateformes détectées, dans l'ordre."""
    for name in detected():
        implementation = implementations.get(name)
        value = read(implementation) if implementation else None
        if value:
            return value
    return None

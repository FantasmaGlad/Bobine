"""Réglages de l'application : chaque module inscrit ses routes sur le routeur commun de `core`."""
from . import access, backup, display, laptop_lid, maintenance, values, wired_mode
from .core import router, stored_language

__all__ = [
    "access", "backup", "display", "laptop_lid", "maintenance", "values", "wired_mode",
    "router", "stored_language",
]

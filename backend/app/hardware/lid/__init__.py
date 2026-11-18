"""Capot d'ordinateur portable : présence et maintien de l'activité capot fermé."""
from .registry import has_lid, prevent_sleep, set_prevent_sleep

__all__ = ["has_lid", "prevent_sleep", "set_prevent_sleep"]

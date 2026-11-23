"""Actions rapides du clic droit (application web installée, lanceur du bureau, plateau) : liste unique."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuickAction:
    id: str
    path: str
    name: str
    name_en: str


QUICK_ACTIONS: tuple[QuickAction, ...] = (
    QuickAction("admin", "/", "Ouvrir l'administration", "Open the administration"),
    QuickAction("grid", "/grid", "Ouvrir le pupitre tactile", "Open the touch panel"),
    QuickAction("cinema", "/cinema", "Ouvrir l'écran cinéma", "Open the cinema screen"),
    QuickAction("visuals", "/visuals", "Diffuser un visuel", "Show a visual"),
)

"""Avis de changement de la bibliothèque vidéo aux clients connectés."""

from app.utils.ws_manager import manager as ws_manager


def notify_library(reason: str) -> None:
    ws_manager.broadcast_threadsafe({"event": "library_change", "reason": reason})

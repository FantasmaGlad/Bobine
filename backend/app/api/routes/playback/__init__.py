"""Lecture : état, reprise, WebSocket des écrans, commandes vidéo et radio, façade REST."""
# L'import des modules inscrit leurs routes et câble les moteurs : aucun ne doit être retiré d'ici.
from . import cinema, commands, facade, media_items, radio_commands, socket, state, wiring
from .core import router
from .facade import command_router

__all__ = [
    "cinema", "commands", "facade", "media_items", "radio_commands", "socket", "state", "wiring",
    "router", "command_router",
]

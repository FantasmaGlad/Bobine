"""Sockets réseau : options d'écoute propres à chaque plateforme."""
from .registry import prepare_listen_socket

__all__ = ["prepare_listen_socket"]

import os
import socket
import sys

from . import posix, windows


def _platform():
    return posix if os.name == "posix" and sys.platform != "cygwin" else windows


def prepare_listen_socket(sock: socket.socket) -> None:
    """Options d'un socket d'écoute : réutilisation de l'adresse sous POSIX, où elle n'autorise pas deux écoutes actives."""
    _platform().prepare_listen_socket(sock)

"""Commande `bobine` : piloter et diagnostiquer Bobine sans navigateur, en local ou sur une machine du réseau."""
from .client import Client, local_version
from .core import COMMANDS, EXIT_ERROR, EXIT_OK, EXIT_REFUSED, EXIT_UNREACHABLE, EXIT_USAGE, CliError
from .entry import main
from .parser import build_parser

__all__ = [
    "COMMANDS", "EXIT_ERROR", "EXIT_OK", "EXIT_REFUSED", "EXIT_UNREACHABLE", "EXIT_USAGE",
    "CliError", "Client", "build_parser", "local_version", "main",
]

"""Commande `bobine` : piloter et diagnostiquer Bobine sans navigateur, en local ou sur une machine du réseau.

Client HTTP de l'API (mêmes routes que l'interface, aucune logique propre), bibliothèque standard seulement : la
commande démarre vite et marche aussi sur l'appliance. Sortie minimale par défaut, `-v` et `-vv` pour le détail sur
stderr, `--json` pour la réponse de l'API sur stdout (`status`, qui fait deux requêtes, rend `health` et `playback`). Codes
de sortie : 0 succès, 1 erreur ou problème trouvé, 2 usage (400, 422), 3 Bobine injoignable, 4 refus (403, 404, 409, 503 :
canal verrouillé, élément introuvable...).
"""
from .client import Client, local_version
from .core import COMMANDS, EXIT_ERROR, EXIT_OK, EXIT_REFUSED, EXIT_UNREACHABLE, EXIT_USAGE, CliError
from .entry import main
from .parser import build_parser

__all__ = [
    "COMMANDS", "EXIT_ERROR", "EXIT_OK", "EXIT_REFUSED", "EXIT_UNREACHABLE", "EXIT_USAGE",
    "CliError", "Client", "build_parser", "local_version", "main",
]

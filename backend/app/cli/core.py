"""Socle de la ligne de commande : codes de sortie, erreur typée, sortie texte ou JSON, lecture des paramètres."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from app.cli.specs import SPECS

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_UNREACHABLE, EXIT_REFUSED, EXIT_NOT_FOUND = 0, 1, 2, 3, 4, 5
_BUILT_IN = ("status", "diagnose", "library", "playlists", "schedule", "devices", "storage", "metrics", "imports", "display", "logs",
             "playback", "radio", "config", "settings", "update", "completion", "api", "open", "version")
COMMANDS = tuple(dict.fromkeys(_BUILT_IN + tuple(spec.command for spec in SPECS)))
_REFUSAL_STATUSES = {403, 409, 503}
DEFAULT_TIMEOUT = 30.0


class CliError(Exception):
    def __init__(self, message: str, code: int = EXIT_ERROR, payload: Any = None) -> None:
        super().__init__(message)
        self.code, self.payload = code, payload


class Output:
    def __init__(self, args: argparse.Namespace) -> None:
        self.json = args.json
        self.verbosity = -1 if args.quiet else args.verbose
        self.color = sys.stdout.isatty() and not args.no_color and "NO_COLOR" not in os.environ

    def log(self, level: int, message: str) -> None:
        if self.verbosity >= level:
            print(message, file=sys.stderr)

    def paint(self, text: str, color: str) -> str:
        codes = {"red": "31", "yellow": "33", "green": "32", "dim": "2"}
        return f"\033[{codes[color]}m{text}\033[0m" if self.color else text

    def result(self, payload: Any, human: str | None = None) -> None:
        if self.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif human and self.verbosity >= 0:
            print(human)


def segment(value: object) -> str:
    """Un identifiant inséré dans un chemin d'URL : jamais de `/`, `?`, `#` ou `..` pris pour de la structure."""
    return urllib.parse.quote(str(value), safe="")


def parse_params(pairs: list[str]) -> dict[str, Any]:
    """`video_id=12 volume=40 subtitle=off` : la valeur est lue en JSON quand c'est possible, sinon en texte."""
    params: dict[str, Any] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key:
            raise CliError(f"paramètre invalide : {pair!r} (attendu clé=valeur)", EXIT_USAGE)
        try:
            params[key] = json.loads(value)
        except ValueError:
            params[key] = value
    return params

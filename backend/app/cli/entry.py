"""Point d'entrée : préparation de la sortie, exécution d'une commande, code de retour."""

from __future__ import annotations

import json
import os
import sys

from .client import Client, _default_port, _timeout
from .core import EXIT_ERROR, EXIT_USAGE, CliError, Output
from .parser import build_parser


def _prepare_windows_output() -> None:
    """Sous Windows, une sortie redirigée utilise la page de code ANSI (cp1252 en français) : un titre ou un journal
    non latin ferait échouer `print`. Le remplacement par des échappements Unicode garde un JSON valide et évite la
    traceback ; la console, elle, reste en Unicode."""
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _prepare_windows_output()
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return EXIT_USAGE
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse : 0 pour --help et --version, 2 pour une erreur d'usage
        return int(exc.code or 0)
    out = Output(args)
    try:
        host = args.host or os.environ.get("BOBINE_HOST", "127.0.0.1")
        port = args.port if args.port is not None else _default_port()
        if not 1 <= port <= 65535:
            raise CliError(f"port invalide : {port} (1 à 65535).", EXIT_USAGE)
        client = Client(host, port, out, _timeout(args))
        return args.run(client, out, args)
    except CliError as exc:
        if out.json and exc.payload is not None:
            print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        print(f"bobine : {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130
    except (TypeError, AttributeError, KeyError, IndexError, ValueError) as exc:
        # Réponse 200 de forme inattendue (vide, `null`, champ absent) : un message, pas une traceback.
        out.log(1, f"{type(exc).__name__} : {exc}")
        print(f"bobine : réponse inattendue de Bobine ({type(exc).__name__}). Relancez avec -v pour le détail ; "
              "la version de la commande et celle du serveur diffèrent peut-être.", file=sys.stderr)
        return EXIT_ERROR


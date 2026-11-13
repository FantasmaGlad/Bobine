from __future__ import annotations

import argparse
from typing import Any

from app.cli.core import EXIT_ERROR, EXIT_NOT_FOUND, EXIT_OK, EXIT_REFUSED, EXIT_UNREACHABLE, EXIT_USAGE

EXIT_CODES = (
    (EXIT_OK, "succès"),
    (EXIT_ERROR, "échec de l'opération ou problème détecté"),
    (EXIT_USAGE, "arguments ou valeur invalides"),
    (EXIT_UNREACHABLE, "Bobine injoignable"),
    (EXIT_REFUSED, "refusé par l'état courant (conflit, interdit, indisponible)"),
    (EXIT_NOT_FOUND, "cible introuvable"),
)


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    return next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)


def _argument(action: argparse.Action) -> dict[str, Any]:
    return {
        "name": action.option_strings[-1] if action.option_strings else action.dest,
        "help": action.help or "",
        "positional": not action.option_strings,
        "choices": list(action.choices) if action.choices else None,
        "repeat": isinstance(action, argparse._AppendAction) or action.nargs in ("+", "*"),
        "flag": action.nargs == 0,
    }


def _arguments(parser: argparse.ArgumentParser, globals_: set[str]) -> list[dict[str, Any]]:
    return [_argument(a) for a in parser._actions
            if not isinstance(a, (argparse._HelpAction, argparse._SubParsersAction, argparse._VersionAction))
            and not (set(a.option_strings) & globals_)]


def _helps(sub: argparse._SubParsersAction) -> dict[str, str]:
    return {choice.dest: choice.help or "" for choice in sub._choices_actions}


def cli_reference(parser: argparse.ArgumentParser) -> dict[str, Any]:
    root = _subparsers(parser)
    globals_ = {o for a in parser._actions for o in a.option_strings}
    commands = []
    for name, command in root.choices.items():
        sub = _subparsers(command)
        actions = [{"name": action, "help": _helps(sub).get(action, ""), "arguments": _arguments(p, globals_)}
                   for action, p in sub.choices.items()] if sub else []
        commands.append({"name": name, "help": _helps(root).get(name, ""), "arguments": _arguments(command, globals_),
                         "actions": actions})
    return {
        "options": _arguments(parser, set()),
        "exit_codes": [{"code": code, "meaning": meaning} for code, meaning in EXIT_CODES],
        "commands": sorted(commands, key=lambda c: c["name"]),
    }

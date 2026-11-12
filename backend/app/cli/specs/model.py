from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


class UsageError(ValueError):
    pass


@dataclass(frozen=True)
class Arg:
    flags: tuple[str, ...]
    help: str = ""
    kind: Callable[[str], Any] | None = None
    choices: tuple[str, ...] | None = None
    action: str | None = None
    default: Any = None
    nargs: str | None = None
    dest: str | None = None

    def add_to(self, parser: argparse.ArgumentParser) -> None:
        options: dict[str, Any] = {"help": self.help}
        if self.action:
            options["action"] = self.action
        else:
            if self.kind:
                options["type"] = self.kind
            if self.choices:
                options["choices"] = self.choices
            if self.nargs:
                options["nargs"] = self.nargs
        if self.default is not None:
            options["default"] = self.default
        if self.dest and self.flags[0].startswith("-"):
            options["dest"] = self.dest
        parser.add_argument(*self.flags, **options)


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    body: Any = None
    query: dict | None = None
    files: tuple[tuple[str, Path], ...] = ()


@dataclass(frozen=True)
class Spec:
    command: str
    action: str
    help: str
    request: Callable[[Any, argparse.Namespace], Call]
    covers: tuple[str, ...]
    arguments: tuple[Arg, ...] = ()
    human: Callable[[Any, argparse.Namespace], str] = lambda payload, args: "Fait."
    confirm: str | None = None
    needs_one_of: tuple[str, ...] = field(default=())

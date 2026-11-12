from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .model import Arg, Call, Spec, UsageError
from .render import summary

_FIELD = re.compile(r"^(?P<name>[a-z_]+)(?::(?P<kind>int|float|bool|ints|strs|json))?(?:=(?P<choices>[\w|.:-]+))?$")
_TEXT_IDS = {"device_id", "upload_id", "job_id"}
_RESERVED = {"host", "port", "json", "verbose", "quiet", "timeout", "yes", "run", "spec", "command", "no_color"}
_TRUE, _FALSE = {"1", "true", "on", "oui", "yes"}, {"0", "false", "off", "non", "no"}


def _bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE | _FALSE:
        return value in _TRUE
    raise UsageError(f"booléen attendu (on/off, true/false) : {raw!r}")


def _ints(raw: str) -> list[int]:
    try:
        return [int(part) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise UsageError(f"liste d'entiers attendue (1,2,3) : {raw!r}") from exc


def _json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise UsageError(f"JSON invalide : {exc}") from exc


_PARSERS: dict[str | None, Callable[[str], Any]] = {
    None: str, "int": int, "float": float, "bool": _bool, "ints": _ints, "json": _json,
    "strs": lambda raw: [part.strip() for part in raw.split(",") if part.strip()],
}


@dataclass(frozen=True)
class Field:
    name: str
    kind: str | None
    choices: tuple[str, ...] | None
    positional: bool

    @classmethod
    def parse(cls, text: str, positional: set[str]) -> "Field":
        match = _FIELD.match(text)
        if not match:
            raise ValueError(f"champ mal décrit : {text}")
        choices = tuple(match["choices"].split("|")) if match["choices"] else None
        return cls(match["name"], match["kind"], choices, match["name"] in positional)

    @property
    def dest(self) -> str:
        return f"for_{self.name}" if self.name in _RESERVED else self.name

    def arg(self) -> Arg:
        flag = self.dest if self.positional else "--" + self.dest.replace("_", "-")
        kind = None if self.kind in ("bool", "ints", "strs", "json") else _PARSERS[self.kind]
        return Arg((flag,), self.kind or "", kind, self.choices, dest=self.dest)

    def provided(self, args: Any) -> bool:
        return getattr(args, self.dest, None) is not None

    def value(self, args: Any) -> Any:
        raw = getattr(args, self.dest, None)
        if raw is None or self.kind not in ("bool", "ints", "strs", "json"):
            return raw
        return _PARSERS[self.kind](raw)


def _paths(value: Any) -> list[str]:
    return list(value) if isinstance(value, list) else [value]


def _path_arg(name: str) -> Arg:
    kind = int if (name == "id" or name.endswith("_id")) and name not in _TEXT_IDS else None
    return Arg((name,), name, kind)


def route(
    command: str, action: str, method: str, path: str, help: str, *,
    body: tuple[str, ...] = (), query: tuple[str, ...] = (), pos: tuple[str, ...] = (), files: tuple[str, ...] = (),
    confirm: str | None = None, human: Callable[[Any, Any], str] = summary, require_one: bool = False, raw: str | None = None,
    text: bool = False,
) -> Spec:
    positional = set(pos)
    params = re.findall(r"{(\w+)}", path)
    body_fields = tuple(Field.parse(text, positional) for text in body)
    query_fields = tuple(Field.parse(text, positional) for text in query)
    arguments = tuple(_path_arg(name) for name in params)
    arguments += tuple(Arg((name.rstrip("+"),), "fichier(s)", nargs="+" if name.endswith("+") else None) for name in files)
    arguments += tuple(f.arg() for f in sorted(body_fields + query_fields, key=lambda f: not f.positional))

    def request(client: Any, args: Any) -> Call:
        target = path.format(**{name: urllib.parse.quote(str(getattr(args, name)), safe="") for name in params})
        payload = {f.name: f.value(args) for f in body_fields if f.provided(args)}
        params_ = {f.name: f.value(args) for f in query_fields if f.provided(args)}
        attached = tuple((name.rstrip("+"), Path(raw)) for name in files for raw in _paths(getattr(args, name.rstrip("+"))))
        content = payload.get(raw) if raw else payload if body_fields else None
        return Call(method, target, content, params_ or None, attached, text)

    optional = tuple(f.dest for f in body_fields + query_fields if not f.positional)
    return Spec(command, action, help, request, (f"{method} {path}",), arguments, human, confirm,
                optional if require_one else ())

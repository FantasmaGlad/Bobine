"""Lecture et validation des valeurs d'un fichier, sans accès à la base."""
from __future__ import annotations
import difflib
import json
import re
from typing import Any
from app import config_files
from app.utils.uid import is_uid
from app.config_apply.context import _Context


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _names(ctx: _Context, file: str, entries: list) -> bool:
    names = [e.get("name") for e in entries if isinstance(e, dict)]
    if any(not isinstance(n, str) or not n.strip() for n in names) or len(names) != len(entries):
        ctx.fail(file, "chaque playlist doit avoir un nom")
        return False
    for name in config_files._duplicates(names):
        ctx.fail(file, f"playlist « {name} » présente deux fois")
    for uid in config_files._duplicates(e.get("uid") for e in entries if is_uid(e.get("uid"))):
        ctx.fail(file, f"uid {uid} présent deux fois")
    return True


def _list(ctx: _Context, file: str, document: dict, key: str) -> list:
    value = document.get(key)
    if not isinstance(value, list):
        ctx.fail(file, f"« {key} » doit être une liste")
        return []
    return value


def _flag(ctx: _Context, file: str, label: str, value: Any) -> bool:
    """Booléen JSON strict : la chaîne « false » ne doit pas valoir vrai par simple vérité Python."""
    if not isinstance(value, bool):
        ctx.fail(file, f"{label} doit être un booléen (true ou false)")
        return False
    return value


def _text(ctx: _Context, file: str, label: str, value: Any, *, required: bool = False) -> tuple[bool, str | None]:
    """(valide, valeur nettoyée) : une chaîne vide efface un champ facultatif ; un champ obligatoire ne peut pas l'être."""
    if value is None and not required:
        return True, None
    if not isinstance(value, str):
        ctx.fail(file, f"{label} doit être un texte : {value!r}")
        return False, None
    value = value.strip()
    if required and not value:
        ctx.fail(file, f"{label} ne peut pas être vide")
        return False, None
    return True, value or None


def _integer(ctx: _Context, file: str, label: str, value: Any) -> tuple[bool, int | None]:
    if value is None:
        return True, None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        ctx.fail(file, f"{label} doit être un entier positif : {value!r}")
        return False, None
    return True, value


def _strip_uids(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_uids(v) for k, v in value.items() if k != "uid"}
    if isinstance(value, list):
        return [_strip_uids(v) for v in value]
    return value


def _without_links(document: dict) -> dict:
    links = ("chapters", "chapters_source", "chapters_file", "subtitles", "subtitle_files")
    return {**document, "videos": [{k: v for k, v in entry.items() if k not in links} if isinstance(entry, dict) else entry
                                  for entry in document.get("videos") or []]}


def _diff(name: str, before: dict, wanted: dict) -> list[str]:
    ignored = ("warnings", "prune", "schema")
    clean = {k: v for k, v in wanted.items() if k not in ignored}
    current = {k: v for k, v in before.items() if k not in ignored}
    if name == "library/videos.json":
        # Liens vers les chapitres et sous-titres : informatifs, jamais appliqués, donc absents de l'écart.
        clean, current = _without_links(clean), _without_links(current)
    if '"uid"' not in json.dumps(clean):
        # Document de la version 5.1, sans `uid` : l'écart ne porte pas sur les identifiants.
        current = _strip_uids(current)
    if clean == current:
        return []
    return list(difflib.unified_diff(
        config_files.dumps(current).splitlines(), config_files.dumps(clean).splitlines(),
        fromfile=f"actuel/{name}", tofile=f"demandé/{name}", lineterm="", n=1,
    ))

"""Contexte d'une application : session, erreurs accumulées, effets à chaud, identifiants réservés."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Awaitable, Callable
from sqlalchemy.orm import Session
from app.utils.uid import is_uid


class ConfigErrors(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


class _Context:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.errors: list[str] = []
        self.effects: list[Callable[[Session], Awaitable[None]]] = []
        self.restart_required: list[str] = []

    def fail(self, file: str, message: str) -> None:
        self.errors.append(f"{file} : {message}")


def _pick(ctx: _Context, file: str, what: str, candidates: list, ref: dict, path_of: Callable[[Any], str | None]):
    wanted = (ref or {}).get("file")
    if wanted:
        candidates = [c for c in candidates if path_of(c) and Path(path_of(c)).name == wanted]
    if len(candidates) == 1:
        return candidates[0]
    ctx.fail(file, f"{what} {'introuvable' if not candidates else 'ambigu (préciser « file »)'} : {json.dumps(ref, ensure_ascii=False)}")
    return None


def _by_uid(ctx: _Context, model, ref: Any):
    uid = ref.get("uid") if isinstance(ref, dict) else None
    return ctx.db.query(model).filter(model.uid == uid).first() if is_uid(uid) else None


def _claim_uid(ctx: _Context, model, entry: Any, obj: Any) -> None:
    uid = entry.get("uid") if isinstance(entry, dict) else None
    if is_uid(uid, getattr(model, "__uid_prefix__", None)) and not ctx.db.query(model).filter(model.uid == uid).first():
        obj.uid = uid

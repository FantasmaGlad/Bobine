"""Point d'entrée : validation complète, écriture en une transaction, puis effets à chaud ou écart à blanc."""
from __future__ import annotations
from typing import Any, Awaitable, Callable
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app import config_files
from app import config_builders
from app import config_mirror
from app.config_apply.context import ConfigErrors, _Context
from app.config_apply.registry import APPLIERS, ORDER
from app.config_apply.values import _diff


async def apply(db: Session, files: dict[str, Any], *, dry_run: bool, include_machine: bool) -> dict[str, Any]:
    """Valide et applique `{nom de fichier: document}` ; lève `ConfigErrors` (rien n'est écrit) si un élément est invalide."""
    result, effects = await run_in_threadpool(_validate_and_write, db, files, dry_run, include_machine)
    for effect in effects:
        await effect(db)
    if not dry_run:
        config_mirror.schedule_mirror()
    return result


def _canonical_files(files: dict[str, Any]) -> dict[str, Any]:
    renamed: dict[str, Any] = {}
    errors = []
    for key, document in files.items():
        name = config_files.canonical_name(str(key))
        if name == "manifest.json":
            continue
        if name in renamed:
            errors.append(f"{name} fourni deux fois (nom plat et arborescence)")
        renamed[name] = document
    errors += [f"fichier inconnu : {name}" for name in sorted(set(renamed) - set(APPLIERS))]
    if errors:
        raise ConfigErrors(errors)
    return renamed


def _header_error(name: str, document: Any) -> str | None:
    if not isinstance(document, dict) or document.get("schema") not in config_files.ACCEPTED_SCHEMAS:
        return f"« schema » doit valoir {' ou '.join(map(str, config_files.ACCEPTED_SCHEMAS))}"
    if document.get("kind") != config_files.KINDS[name]:
        return f"« kind » doit valoir {config_files.KINDS[name]}"
    return None


def _apply_document(db: Session, ctx: _Context, name: str, document: dict) -> None:
    with db.no_autoflush:
        try:
            APPLIERS[name](ctx, name, document)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError, SQLAlchemyError) as exc:
            ctx.fail(name, f"document invalide : {exc}")
    if not ctx.errors:
        try:
            db.flush()
        except Exception as exc:
            ctx.fail(name, f"écriture refusée par la base : {exc}")


def _finish(db: Session, ctx: _Context, dry_run: bool) -> None:
    if ctx.errors:
        db.rollback()
        raise ConfigErrors(ctx.errors)
    try:
        db.flush()
    except Exception as exc:
        db.rollback()
        raise ConfigErrors([f"écriture refusée par la base : {exc}"]) from exc
    if dry_run:
        db.rollback()
    else:
        db.commit()


def _validate_and_write(
    db: Session, files: dict[str, Any], dry_run: bool, include_machine: bool,
) -> tuple[dict[str, Any], list[Callable[[Session], Awaitable[None]]]]:
    files = _canonical_files(files)
    ctx = _Context(db)
    skipped = []
    changes: dict[str, list[str]] = {}
    for name in (name for name in ORDER if name in files):
        document = files[name]
        if name == "machine.json" and not include_machine:
            skipped.append(name)
            continue
        error = _header_error(name, document)
        if error:
            ctx.fail(name, error)
            continue
        changes[name] = _diff(name, config_builders.BUILDERS[name](db), document)
        _apply_document(db, ctx, name, document)
    _finish(db, ctx, dry_run)
    result = {
        "applied": not dry_run,
        "changes": {name: lines for name, lines in changes.items() if lines},
        "skipped": skipped,
        "restart_required": sorted(set(ctx.restart_required)),
    }
    return result, ([] if dry_run else ctx.effects)

"""Point d'entrée : validation complète, écriture en une transaction, puis effets à chaud ou écart à blanc."""
from __future__ import annotations
from typing import Any, Awaitable, Callable
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app import config_files
from app.config_apply.context import ConfigErrors, _Context
from app.config_apply.registry import APPLIERS, ORDER
from app.config_apply.values import _diff


async def apply(db: Session, files: dict[str, Any], *, dry_run: bool, include_machine: bool) -> dict[str, Any]:
    """Valide et applique `{nom de fichier: document}` ; lève `ConfigErrors` (rien n'est écrit) si un élément est
    invalide. Renvoie l'écart par fichier, ce qui a été ignoré et ce qui demande un redémarrage. La validation et
    l'écriture tournent hors de la boucle d'événements : un gros document ne fige ni les flux ni les écrans ; seuls
    les effets à chaud (diffusions, moteurs) reviennent sur la boucle."""
    result, effects = await run_in_threadpool(_validate_and_write, db, files, dry_run, include_machine)
    for effect in effects:
        await effect(db)
    if not dry_run:
        config_files.schedule_mirror()
    return result


def _validate_and_write(
    db: Session, files: dict[str, Any], dry_run: bool, include_machine: bool,
) -> tuple[dict[str, Any], list[Callable[[Session], Awaitable[None]]]]:
    renamed: dict[str, Any] = {}
    errors = []
    for key, document in files.items():
        name = config_files.canonical_name(str(key))
        if name == "manifest.json":
            continue  # index de l'export : rien à appliquer
        if name in renamed:
            errors.append(f"{name} fourni deux fois (nom plat et arborescence)")
        renamed[name] = document
    files = renamed
    errors += [f"fichier inconnu : {name}" for name in sorted(set(files) - set(APPLIERS))]
    if errors:
        raise ConfigErrors(errors)
    ctx = _Context(db)
    skipped = []
    changes: dict[str, list[str]] = {}
    for name in ORDER:
        if name not in files:
            continue
        document = files[name]
        if name == "machine.json" and not include_machine:
            skipped.append(name)
            continue
        if not isinstance(document, dict) or document.get("schema") not in config_files.ACCEPTED_SCHEMAS:
            ctx.fail(name, f"« schema » doit valoir {' ou '.join(map(str, config_files.ACCEPTED_SCHEMAS))}")
            continue
        if document.get("kind") != config_files.KINDS[name]:
            ctx.fail(name, f"« kind » doit valoir {config_files.KINDS[name]}")
            continue
        changes[name] = _diff(name, config_files.BUILDERS[name](db), document)
        with db.no_autoflush:
            try:
                APPLIERS[name](ctx, name, document)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError, SQLAlchemyError) as exc:
                # Un document JSON mal typé (liste au lieu d'objet, chaîne au lieu d'entier...) est une erreur de
                # validation : il ne doit jamais produire un 500. La transaction est annulée plus bas comme pour
                # toute autre erreur.
                ctx.fail(name, f"document invalide : {exc}")
        if not ctx.errors:
            # Rendus visibles dans la transaction (non validée) : un fichier suivant peut citer ce qui vient d'être créé.
            try:
                db.flush()
            except Exception as exc:
                ctx.fail(name, f"écriture refusée par la base : {exc}")
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
    result = {
        "applied": not dry_run,
        "changes": {name: lines for name, lines in changes.items() if lines},
        "skipped": skipped,
        "restart_required": sorted(set(ctx.restart_required)),
    }
    return result, ([] if dry_run else ctx.effects)

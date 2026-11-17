"""Miroir sur disque des fichiers de configuration, réécrit peu après chaque changement."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config_builders import export_all
from app.config_files import LEGACY_NAMES, dumps

logger = logging.getLogger(__name__)


MIRROR_DELAY_SECONDS = 2.0


_mirror_lock = threading.Lock()


_mirror_timer: threading.Timer | None = None


def mirror_dir() -> Path:
    """`config/` à côté des journaux, dans le dossier de données de Bobine (jamais dans le dossier du code, qui est un dépôt git sur l'appliance)."""
    from app.config import settings as runtime_settings

    return Path(runtime_settings.logs_dir).parent / "config"


def write_mirror() -> int:
    """Réécrit les fichiers dont le contenu a changé (écriture atomique) ; renvoie leur nombre."""
    from app.database import SessionLocal

    target = mirror_dir()
    target.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        documents = export_all(db)
    written = 0
    for name, document in documents.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = dumps(document)
        try:
            if path.read_text(encoding="utf-8") == content:
                continue
        except OSError:
            pass
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as out:
                out.write(content)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        written += 1
    for legacy in LEGACY_NAMES:
        (target / legacy).unlink(missing_ok=True)
    return written


def _mirror_now() -> None:
    global _mirror_timer
    with _mirror_lock:
        _mirror_timer = None
    try:
        write_mirror()
    except Exception as exc:
        logger.warning("Copie de la configuration dans %s impossible : %s", mirror_dir(), exc)


def schedule_mirror() -> None:
    """Demande une mise à jour de la copie ; plusieurs demandes rapprochées n'en font qu'une."""
    global _mirror_timer
    with _mirror_lock:
        if _mirror_timer is not None:
            _mirror_timer.cancel()
        _mirror_timer = threading.Timer(MIRROR_DELAY_SECONDS, _mirror_now)
        _mirror_timer.daemon = True
        _mirror_timer.start()


class ConfigMirrorTrigger:
    """Après chaque requête réussie qui modifie quelque chose sous `/api/`, demande la mise à jour de la copie : un seul point d'accroche pour toutes les routes, présentes et futures."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS") or not scope.get("path", "").startswith("/api/"):
            await self.app(scope, receive, send)
            return
        status = 0

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        await self.app(scope, receive, capture)
        if 200 <= status < 300:
            schedule_mirror()

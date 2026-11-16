"""Provenance des requêtes et traduction des erreurs du pilote pour les routes des périphériques."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, TypeVar

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.api.network_guard import has_forwarding_headers
from app.devices import locality
from app.devices.base import DeviceError
from app.utils.activity_log import log_activity

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def is_local_request(request: Request) -> bool:
    """Requête venant de la machine elle-même (écran physique)."""
    if has_forwarding_headers(request.scope.get("headers") or ()):
        return False
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
    if host.endswith(".onion"):
        return False
    return locality.is_local_client(_client_ip(request))


def fail(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


@dataclass
class Access:
    local: bool
    ip: str


def require_access(request: Request) -> Access:
    """Provenance de la requête ; ne refuse jamais (réseau local de confiance)."""
    return Access(local=is_local_request(request), ip=_client_ip(request))


async def guard(coro: Awaitable[T]) -> T:
    try:
        return await coro
    except DeviceError as exc:
        raise fail(exc.status, exc.code, exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Erreur inattendue du pilote de périphériques : %s", exc, exc_info=True)
        raise fail(502, "driver_error", "Le système n'a pas pu exécuter cette opération.") from exc


async def translate(coro: Awaitable[T]) -> T:
    """Erreurs de validation d'un moteur traduites en réponse ; toute autre erreur suit le gestionnaire global."""
    try:
        return await coro
    except DeviceError as exc:
        raise fail(exc.status, exc.code, exc.message) from exc


def log(db: Session, event: str, detail: str | None = None) -> None:
    log_activity(db, event, detail)

"""Socle de la lecture : routeur, moteurs par canal, refus typé d'une commande."""

import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.api.contract import CHANNELS, DEFAULT_CHANNEL
from app.playback.manager import init_playback_managers
from app.radio_manager import (
    init_radio_managers,
)
from app.utils.activity_log import log_activity
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)


router = APIRouter(tags=["playback"])

_cinema_sessions: dict[str, int] = {}

playback_managers = init_playback_managers(ws_manager.broadcast)
radio_managers = init_radio_managers(ws_manager.broadcast)


def _resolve_channel(value) -> str:
    return value if value in CHANNELS else DEFAULT_CHANNEL


class CommandRejected(Exception):
    """Commande refusée sans rien changer."""

    def __init__(self, reason: str, channel: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.reason, self.channel, self.message, self.status = reason, channel, message, status


async def _reject_unavailable(command: str, channel: str, title: str | None, db) -> None:
    logger.info(f"Commande {command} refusée : « {title} » est sur un support externe indisponible")
    await run_in_threadpool(log_activity, db, "media_unavailable", title)
    raise CommandRejected("storage_unavailable", channel, f"« {title} » est sur un support externe indisponible.", 503)


def _not_found(command: str, channel: str, what: str) -> CommandRejected:
    logger.warning(f"Commande {command} : {what} introuvable")
    return CommandRejected("not_found", channel, f"{what} introuvable.", 404)

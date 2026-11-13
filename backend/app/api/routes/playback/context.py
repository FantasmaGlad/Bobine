"""Contexte d'une commande de lecture vidéo ou audio, partagé par ses gestionnaires."""

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.routes.settings.display import get_display_output_value
from app.utils.activity_log import log_activity
from app.utils.ws_manager import manager as ws_manager

from .core import CommandRejected, _not_found

logger = logging.getLogger(__name__)


@dataclass
class Command:
    name: str
    params: dict
    client_ts: Any
    db: Session
    websocket: WebSocket | None
    is_kiosk: bool
    channel: str
    manager: Any

    def number(self, key: str, default: float = 0) -> float:
        return float(self.params.get(key) or default)

    def not_found(self, label: str) -> CommandRejected:
        return _not_found(self.name, self.channel, label)

    def secondary_kiosk(self) -> bool:
        return self.is_kiosk and self.websocket is not None and not ws_manager.is_primary_kiosk(self.websocket)

    async def fetch(self, model, ident):
        return await run_in_threadpool(lambda: self.db.query(model).filter(model.id == ident).first())

    async def log(self, event: str, title: str | None) -> None:
        await run_in_threadpool(log_activity, self.db, event, title)

    async def ensure_not_locked(self) -> None:
        output = await run_in_threadpool(get_display_output_value, self.db, self.channel)
        if output not in ("cinema", "radio"):
            return
        reason = "cinema_locked" if output == "cinema" else "radio_locked"
        logger.info(f"Commande {self.name} ignorée : le canal '{self.channel}' est en mode {output} (verrouillé)")
        raise CommandRejected(reason, self.channel,
                              f"Le canal {self.channel} affiche le mode {output} : aucun écran vidéo ne montrerait ce lancement.")

    def ensure_cable(self) -> None:
        if self.channel != "cable":
            logger.info(f"Commande {self.name} ignorée : le mode coach est réservé au canal câblé")
            raise CommandRejected("coach_cable_only", self.channel, "Le mode coach est réservé au canal câblé.")

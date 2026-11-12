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

# Suivi des sessions de lecture actives pour les sorties /cinema par canal
_cinema_sessions: dict[str, int] = {}

# Les PlaybackManagers sont initialisés ici avec le broadcast du
# ConnectionManager : UN ÉTAT PAR CANAL de diffusion — le canal câblé (écran du Wyse) et le canal
# réseau (autres appareils du LAN) ont chacun leur lecture, leur playlist et
# leur planning, totalement indépendants.
playback_managers = init_playback_managers(ws_manager.broadcast)
# Sorties radio : un moteur de lecture INDÉPENDANT par sortie (câblée et
# réseau), même broadcast partagé pour rester sur la même connexion WebSocket
# que les canaux de diffusion ci-dessus.
radio_managers = init_radio_managers(ws_manager.broadcast)


def _resolve_channel(value) -> str:
    """Canal demandé par une commande/requête, replié sur le câblé si absent
    ou invalide (compatibilité avec les clients d'avant la séparation)."""
    return value if value in CHANNELS else DEFAULT_CHANNEL


class CommandRejected(Exception):
    """Commande refusée sans rien changer. `reason` est le vocabulaire de l'évènement WebSocket `command_rejected`
    (`cinema_locked`, `radio_locked`, `coach_cable_only`, `storage_unavailable`, `not_found`, `invalid_params`,
    `empty_library`, `unknown_command`) ; `status` est la réponse de la façade REST."""

    def __init__(self, reason: str, channel: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.reason, self.channel, self.message, self.status = reason, channel, message, status


async def _reject_unavailable(command: str, channel: str, title: str | None, db) -> None:
    """Média d'un support externe débranché : la commande est refusée proprement (jamais une erreur) et journalisée."""
    logger.info(f"Commande {command} refusée : « {title} » est sur un support externe indisponible")
    await run_in_threadpool(log_activity, db, "media_unavailable", title)
    raise CommandRejected("storage_unavailable", channel, f"« {title} » est sur un support externe indisponible.", 503)


def _not_found(command: str, channel: str, what: str) -> CommandRejected:
    logger.warning(f"Commande {command} : {what} introuvable")
    return CommandRejected("not_found", channel, f"{what} introuvable.", 404)

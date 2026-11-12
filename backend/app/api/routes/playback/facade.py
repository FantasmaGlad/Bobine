"""Façade REST des commandes : POST /api/playback/{canal}/{action} et POST /api/radio/{sortie}/{action}."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.contract import PLAYBACK_ACTIONS, RADIO_ACTIONS, RADIO_OUTPUTS
from app.database import get_db
from app.playback_manager import CHANNELS, get_playback_manager
from app.radio_manager import (
    get_radio_manager,
)

from .commands import execute_command
from .core import CommandRejected

command_router = APIRouter(tags=["playback"])

# Rapports d'un écran (position, fins de média, niveaux, route audio) : l'autorité en revient à l'écran primaire
# connecté par WebSocket ; les accepter d'un client REST fausserait l'état. Ils restent hors de la façade.
# Les actions et les sorties de la façade viennent de app.api.contract (partagées avec la commande bobine).
_KIND_MESSAGES = {"channel": "Canal inconnu", "output": "Sortie radio inconnue", "action": "Action inconnue"}


def _rejection_http(command: str, rejected: CommandRejected) -> HTTPException:
    headers = {"Retry-After": "30"} if rejected.status == 503 else None
    return HTTPException(
        status_code=rejected.status,
        detail={"code": rejected.reason, "message": rejected.message, "command": command, "channel": rejected.channel},
        headers=headers,
    )


def _unknown(kind: str, value: str, allowed) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": f"unknown_{kind}", "message": f"{_KIND_MESSAGES[kind]} : {value}.", "allowed": list(allowed)},
    )


@command_router.post("/api/playback/{channel}/{action}")
async def playback_action(
    channel: str, action: str, params: dict[str, Any] | None = Body(default=None), db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Commande de lecture d'un canal (`cable`, `network`) ; corps JSON : les paramètres de la commande WebSocket.
    Réponse : l'état du canal après la commande."""
    if channel not in CHANNELS:
        raise _unknown("channel", channel, CHANNELS)
    if action not in PLAYBACK_ACTIONS:
        raise _unknown("action", action, PLAYBACK_ACTIONS)
    try:
        await execute_command({"command": action, "params": {**(params or {}), "channel": channel}}, db)
    except CommandRejected as rejected:
        raise _rejection_http(action, rejected) from rejected
    return {"channel": channel, "state": get_playback_manager(channel).snapshot()}


@command_router.post("/api/radio/{output}/{action}")
async def radio_action(
    output: str, action: str, params: dict[str, Any] | None = Body(default=None), db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Commande d'une sortie radio (`cable`, `network`) ; même contrat que `/api/playback/{channel}/{action}`."""
    radio_channel = RADIO_OUTPUTS.get(output)
    if radio_channel is None:
        raise _unknown("output", output, RADIO_OUTPUTS)
    if action not in RADIO_ACTIONS:
        raise _unknown("action", action, RADIO_ACTIONS)
    try:
        await execute_command({"command": action, "params": {**(params or {}), "channel": radio_channel}}, db)
    except CommandRejected as rejected:
        raise _rejection_http(action, rejected) from rejected
    return {"output": output, "state": get_radio_manager(radio_channel).snapshot()}

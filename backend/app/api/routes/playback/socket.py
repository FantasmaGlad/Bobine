"""WebSocket des écrans et des tableaux de bord : identification, synchronisation, commandes."""

import logging
import time
from dataclasses import dataclass

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.contract import CHANNELS, DEFAULT_CHANNEL
from app.database import get_db
from app.playback.manager import get_playback_manager
from app.radio_manager import (
    get_all_radio_managers,
    is_radio_channel,
    normalize_radio_channel,
)
from app.utils.boot_state import current_boot_id
from app.utils.ws_manager import manager as ws_manager

from .commands import execute_command
from .core import CommandRejected, _resolve_channel, router

logger = logging.getLogger(__name__)


@dataclass
class _Session:
    is_kiosk: bool = False
    channel: str = DEFAULT_CHANNEL
    client_id: str = ""


async def _send_initial_state(websocket: WebSocket) -> None:
    await websocket.send_json({"event": "boot_id", "boot_id": current_boot_id()})
    managers = [*((c, get_playback_manager(c)) for c in CHANNELS), *get_all_radio_managers().items()]
    for channel, manager in managers:
        await websocket.send_json({"event": "state_change", "cause": "sync", "channel": channel, "data": manager.snapshot()})


async def _identify_kiosk(websocket: WebSocket, session: _Session, params: dict) -> None:
    if not session.is_kiosk:
        session.is_kiosk = True
        requested = params.get("channel")
        session.channel = normalize_radio_channel(requested) if is_radio_channel(requested) else _resolve_channel(requested)
        session.client_id = params.get("client_id") or f"conn-{id(websocket)}"
    is_primary = await ws_manager.register_kiosk(websocket, session.channel, session.client_id)
    ws_manager.set_kiosk_page(websocket, params.get("page") if isinstance(params.get("page"), str) else None)
    await websocket.send_json({"event": "kiosk_role", "is_primary": is_primary})


async def _identify(websocket: WebSocket, session: _Session, params: dict) -> None:
    role = params.get("role")
    if role == "viewer":
        ws_manager.register_viewer(websocket, str(_resolve_channel(params.get("channel"))), str(params.get("page") or "viewer"))
    elif role == "kiosk":
        await _identify_kiosk(websocket, session, params)


async def _execute(websocket: WebSocket, db: Session, session: _Session, message: dict) -> None:
    try:
        await execute_command(message, db, websocket, is_kiosk=session.is_kiosk, default_channel=session.channel)
    except CommandRejected as rejected:
        await websocket.send_json({
            "event": "command_rejected", "command": message.get("command"),
            "reason": rejected.reason, "channel": rejected.channel,
        })
    except WebSocketDisconnect:
        raise
    except Exception as e:
        logger.error(f"Commande WebSocket {message.get('command')} en échec : {e}", exc_info=True)


async def _handle(websocket: WebSocket, db: Session, session: _Session, message: dict) -> None:
    command = message.get("command")
    params = message.get("params") or {}
    if command == "time_sync":
        await websocket.send_json({"event": "time_sync", "t0": params.get("t0"), "server_ms": time.time() * 1000.0})
    elif command == "subscribe":
        requested = params.get("channels")
        if isinstance(requested, list):
            ws_manager.subscribe(websocket, [c for c in requested if isinstance(c, str)])
    elif command == "identify":
        await _identify(websocket, session, params)
    else:
        await _execute(websocket, db, session, message)


@router.websocket("/ws/playback")
async def playback_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await ws_manager.connect(websocket)
    session = _Session()
    try:
        await _send_initial_state(websocket)
        while True:
            await _handle(websocket, db, session, await websocket.receive_json())
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur sur la connexion WebSocket playback : {e}", exc_info=True)
        ws_manager.disconnect(websocket)

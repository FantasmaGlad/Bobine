"""WebSocket des écrans et des tableaux de bord : identification, synchronisation, commandes."""

import logging
import time

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.contract import CHANNELS, DEFAULT_CHANNEL
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


@router.websocket("/ws/playback")
async def playback_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await ws_manager.connect(websocket)
    is_kiosk = False
    kiosk_channel = DEFAULT_CHANNEL
    kiosk_client_id = ""
    try:
        await websocket.send_json({"event": "boot_id", "boot_id": current_boot_id()})
        for channel in CHANNELS:
            await websocket.send_json({
                "event": "state_change",
                "cause": "sync",
                "channel": channel,
                "data": get_playback_manager(channel).snapshot(),
            })
        for radio_channel, radio_manager in get_all_radio_managers().items():
            await websocket.send_json({
                "event": "state_change",
                "cause": "sync",
                "channel": radio_channel,
                "data": radio_manager.snapshot(),
            })
        while True:
            message = await websocket.receive_json()
            if message.get("command") == "time_sync":
                await websocket.send_json({
                    "event": "time_sync",
                    "t0": (message.get("params") or {}).get("t0"),
                    "server_ms": time.time() * 1000.0,
                })
                continue
            if message.get("command") == "subscribe":
                requested = (message.get("params") or {}).get("channels")
                if isinstance(requested, list):
                    ws_manager.subscribe(websocket, [c for c in requested if isinstance(c, str)])
                continue
            if message.get("command") == "identify":
                params = message.get("params") or {}
                role = params.get("role")
                if role == "viewer":
                    ws_manager.register_viewer(websocket, str(_resolve_channel(params.get("channel"))), str(params.get("page") or "viewer"))
                    continue
                if role == "kiosk":
                    if not is_kiosk:
                        is_kiosk = True
                        requested_channel = params.get("channel")
                        kiosk_channel = (
                            normalize_radio_channel(requested_channel)
                            if is_radio_channel(requested_channel)
                            else _resolve_channel(requested_channel)
                        )
                        kiosk_client_id = params.get("client_id") or f"conn-{id(websocket)}"
                    is_primary = await ws_manager.register_kiosk(websocket, kiosk_channel, kiosk_client_id)
                    ws_manager.set_kiosk_page(websocket, params.get("page") if isinstance(params.get("page"), str) else None)
                    await websocket.send_json({
                        "event": "kiosk_role",
                        "is_primary": is_primary,
                    })
                continue
            try:
                await execute_command(message, db, websocket, is_kiosk=is_kiosk, default_channel=kiosk_channel)
            except CommandRejected as rejected:
                await websocket.send_json({
                    "event": "command_rejected", "command": message.get("command"),
                    "reason": rejected.reason, "channel": rejected.channel,
                })
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.error(f"Commande WebSocket {message.get('command')} en échec : {e}", exc_info=True)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur sur la connexion WebSocket playback : {e}", exc_info=True)
        ws_manager.disconnect(websocket)

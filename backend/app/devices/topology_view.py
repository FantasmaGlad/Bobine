"""Carte des périphériques : sources du pilote réunies sans qu'une source absente bloque les autres."""

from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Awaitable

from sqlalchemy.orm import Session

from app.utils.deployment import get_deployment_profile
from app.utils.ws_manager import manager as ws_manager

from . import locality
from .audio_meta import with_listing_meta
from .base import DeviceError
from .topology import build_topology, ethernet_interfaces

logger = logging.getLogger(__name__)


async def _safe(coro: Awaitable[Any]) -> Any:
    try:
        return await coro
    except DeviceError:
        return None
    except Exception as exc:
        logger.debug("Carte des périphériques : source indisponible (%s)", exc)
        return None


async def topology_view(service: Any, db: Session) -> dict[str, Any]:
    driver = service.driver
    audio, bluetooth = await asyncio.gather(_safe(driver.audio_list()), _safe(driver.bluetooth_status()))
    return build_topology(
        machine={"name": socket.gethostname(), "platform": get_deployment_profile()},
        audio=with_listing_meta(audio, db),
        bluetooth=bluetooth,
        ethernets=ethernet_interfaces(),
        clients=ws_manager.client_snapshot(),
        own_ips=locality.own_ip_addresses(),
    )

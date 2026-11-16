"""Garde des changements de Wi-Fi demandés par un client qui passe lui-même par ce Wi-Fi."""

from __future__ import annotations

import ipaddress
from typing import Any

from . import locality
from .base import DeviceError

_ACK_MESSAGE = (
    "Vous êtes connecté à Bobine par ce réseau Wi-Fi : la modification peut couper cet accès. "
    "Confirmez pour continuer ; sans reconfirmation sous 60 s, l'ancien réseau sera rétabli."
)


async def _reached_via_wifi(service: Any, local: bool, ip: str) -> bool:
    if local:
        return False
    subnet = await service.driver.wifi_interface_subnet()
    if not subnet:
        return False
    try:
        return ipaddress.ip_address(locality.normalize_ip(ip) or ip) in ipaddress.ip_network(subnet)
    except ValueError:
        return False


async def require_ack(service: Any, local: bool, ip: str, acknowledged: bool) -> None:
    if not acknowledged and await _reached_via_wifi(service, local, ip):
        raise DeviceError("ack_required", _ACK_MESSAGE, 409)

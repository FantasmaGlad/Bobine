"""Refus des clients venus d'Internet."""
from __future__ import annotations

import ipaddress
import logging
import os
import re
from collections.abc import Iterable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.errors import send_forbidden

from app.utils.local_networks import TRUSTED_NETWORKS

logger = logging.getLogger(__name__)

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def allowed_networks() -> tuple[Network, ...]:
    networks = []
    for raw in os.environ.get("BOBINE_ALLOWED_NETWORKS", "").split(","):
        if raw.strip():
            try:
                networks.append(ipaddress.ip_network(raw.strip(), strict=False))
            except ValueError:
                logger.warning("BOBINE_ALLOWED_NETWORKS : réseau invalide ignoré : %s", raw.strip())
    return tuple(networks)


def is_allowed_client(host: str | None, extra: tuple[Network, ...] = ()) -> bool:
    """Faux seulement pour une adresse IP routable sur Internet et hors des réseaux déclarés."""
    if not host:
        return True
    try:
        address = ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return True
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return any(address in network for network in TRUSTED_NETWORKS + extra)


FORWARDING_HEADERS = (b"x-forwarded-for", b"forwarded", b"x-real-ip", b"cf-connecting-ip", b"true-client-ip")
_FORWARDED_FOR = re.compile(r"for\s*=\s*(\"[^\"]*\"|[^;,\s]*)", re.IGNORECASE)


def forwarded_hosts(headers: Iterable[tuple[bytes, bytes]]) -> list[str] | None:
    """Adresses annoncées par un relais ; `None` sans en-tête de relais, `""` pour une valeur à refuser."""
    found: list[str] | None = None
    for raw_name, raw_value in headers:
        name = raw_name.lower()
        if name not in FORWARDING_HEADERS:
            continue
        found = found if found is not None else []
        value = raw_value.decode("latin-1")
        if name == b"forwarded":
            tokens = [match.strip('"') for match in _FORWARDED_FOR.findall(value)] or [""]
        else:
            tokens = [token.strip() for token in value.split(",")]
        for token in tokens:
            token = token.strip()
            if token.startswith("["):
                token = token[1:].split("]", 1)[0]
            elif token.count(":") == 1:
                token = token.split(":", 1)[0]
            found.append(token)
    return found


def has_forwarding_headers(headers: Iterable[tuple[bytes, bytes]]) -> bool:
    return forwarded_hosts(headers) is not None


def is_allowed_chain(hosts: list[str], extra: tuple[Network, ...] = ()) -> bool:
    for host in hosts:
        try:
            ipaddress.ip_address(host.split("%")[0])
        except ValueError:
            return False
        if not is_allowed_client(host, extra):
            return False
    return True


class LocalNetworkGuard:
    """Refuse (403, ou fermeture 1008 pour un WebSocket) tout client dont l'adresse est publique."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.extra = allowed_networks()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            host = client[0] if client else None
            relayed = forwarded_hosts(scope.get("headers") or ())
            if not is_allowed_client(host, self.extra) or (relayed is not None and not is_allowed_chain(relayed, self.extra)):
                logger.warning("Connexion refusée depuis une adresse publique : %s (relais : %s)", host, relayed)
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                await send_forbidden(send, "public_client", "Bobine n'est joignable que depuis le réseau local ou un VPN (réseaux à ajouter dans BOBINE_ALLOWED_NETWORKS, qui n'ouvre pas le pare-feu).")
                return
        await self.app(scope, receive, send)

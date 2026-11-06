"""Refus des clients venus d'Internet.

Bobine n'a ni mot de passe ni jeton : seul le réseau local est de confiance. Les installateurs n'ouvrent le pare-feu
qu'aux réseaux privés, mais un poste sans pare-feu actif (macOS par défaut, beaucoup de Linux de bureau) et joignable
par une adresse publique serait pilotable depuis Internet. Cette garde refuse donc toute connexion dont l'adresse
source est routable sur Internet, quel que soit le pare-feu.

Admis : boucle locale, réseaux privés (RFC 1918, IPv6 ULA), liens locaux, 100.64.0.0/10 (Tailscale et CGNAT), ainsi
que les réseaux déclarés dans `BOBINE_ALLOWED_NETWORKS` (liste CIDR séparée par des virgules), pour un accès public
volontaire derrière un proxy authentifiant par exemple.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os

from starlette.types import ASGIApp, Receive, Scope, Send

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
        return True  # socket Unix ou client de test : pas d'adresse réseau
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if address in ipaddress.ip_network("100.64.0.0/10"):
        return True
    if not address.is_global:
        return True
    return any(address in network for network in extra)


class LocalNetworkGuard:
    """Refuse (403, ou fermeture 1008 pour un WebSocket) tout client dont l'adresse est publique."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.extra = allowed_networks()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            host = client[0] if client else None
            if not is_allowed_client(host, self.extra):
                logger.warning("Connexion refusée depuis une adresse publique : %s", host)
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                body = json.dumps(
                    {"detail": {"code": "public_client", "message": "Bobine n'est joignable que depuis le réseau local ou un VPN (réseaux à ajouter dans BOBINE_ALLOWED_NETWORKS)."}},
                    ensure_ascii=False,
                ).encode("utf-8")
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"), (b"content-length", str(len(body)).encode())],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)

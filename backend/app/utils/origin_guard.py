"""Refus des requêtes envoyées par une page web d'une autre origine.

Bobine n'a ni mot de passe ni jeton : le réseau local est de confiance. Ce qui reste à empêcher, c'est qu'une page
web quelconque ouverte sur un appareil du réseau pilote l'API à la place de l'utilisateur (désinstallation,
remise à zéro, formatage, lecture). Un navigateur joint toujours l'en-tête `Origin` à une requête qui modifie un
état ou ouvre un WebSocket ; la CLI, l'assistant et `curl` ne l'envoient pas et passent donc sans contrôle.

Comparer `Origin` à `Host` ne suffit pas : par rebinding DNS, une page de `evil.example` dont le nom résout ensuite
vers l'adresse de Bobine envoie des en-têtes identiques. Le nom joint doit donc aussi être un nom qu'aucun tiers ne
peut faire résoudre : adresse IP littérale, nom sans point, suffixe réservé aux réseaux privés, nom de la machine,
ou nom déclaré dans `BOBINE_ALLOWED_HOSTS`.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

# Serveur de développement Next.js (`npm run dev`), qui appelle l'API sur un autre port.
DEFAULT_DEV_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_DEFAULT_PORTS = {"http": 80, "https": 443, "ws": 80, "wss": 443}
# Suffixes jamais délégués dans le DNS public : un tiers ne peut pas les faire résoudre vers une adresse de son choix.
_PRIVATE_SUFFIXES = (".local", ".localhost", ".onion", ".internal", ".home.arpa", ".lan", ".home", ".localdomain")


def dev_origins() -> tuple[str, ...]:
    """Origines tierces admises : `BOBINE_DEV_ORIGINS` (liste séparée par des virgules), sinon le serveur de dev."""
    raw = os.environ.get("BOBINE_DEV_ORIGINS")
    if raw is None:
        return DEFAULT_DEV_ORIGINS
    return tuple(origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip())


def allowed_host_names() -> frozenset[str]:
    """Noms de la machine et noms déclarés dans `BOBINE_ALLOWED_HOSTS` (liste séparée par des virgules)."""
    names = {socket.gethostname(), socket.getfqdn()}
    names.update(os.environ.get("BOBINE_ALLOWED_HOSTS", "").split(","))
    return frozenset(name.strip().lower().rstrip(".") for name in names if name and name.strip())


def is_trusted_host_name(hostname: str, extra_names: frozenset[str] = frozenset()) -> bool:
    """Vrai si `hostname` ne peut pas être un nom de rebinding DNS."""
    name = hostname.lower().rstrip(".")
    try:
        ipaddress.ip_address(name.strip("[]"))
        return True
    except ValueError:
        pass
    return "." not in name or name == "localhost" or name.endswith(_PRIVATE_SUFFIXES) or name in extra_names


def _host_port(netloc: str, scheme: str) -> tuple[str, int] | None:
    try:
        parts = urlsplit(f"//{netloc}")
        port = parts.port
    except ValueError:
        return None
    if not parts.hostname:
        return None
    return parts.hostname.lower(), port or _DEFAULT_PORTS.get(scheme, 80)


def is_same_origin(origin: str, host_header: str, scheme: str) -> bool:
    """Vrai si `origin` désigne le serveur joint par cette requête (même hôte et même port)."""
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False
    origin_hp = _host_port(parts.netloc, parts.scheme)
    request_hp = _host_port(host_header, "https" if scheme in ("https", "wss") else "http")
    return origin_hp is not None and origin_hp == request_hp


class SameOriginGuard:
    """Refuse (403, ou fermeture 1008 pour un WebSocket) toute requête modifiante portant une origine étrangère."""

    def __init__(self, app: ASGIApp, *, allowed_origins: Iterable[str] = ()) -> None:
        self.app = app
        self.allowed_origins = frozenset(origin.rstrip("/") for origin in allowed_origins)
        self.allowed_names = allowed_host_names()

    def _is_allowed(self, scope: Scope) -> bool:
        headers = {key.decode("latin-1"): value.decode("latin-1") for key, value in scope.get("headers", ())}
        origin = headers.get("origin")
        if origin is None:
            return True
        if origin.rstrip("/") in self.allowed_origins:
            return True
        host = headers.get("host", "")
        request_hp = _host_port(host, "http")
        return (
            request_hp is not None
            and is_trusted_host_name(request_hp[0], self.allowed_names)
            and is_same_origin(origin, host, scope.get("scheme", "http"))
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            if not self._is_allowed(scope):
                await send({"type": "websocket.close", "code": 1008})
                return
        elif scope["type"] == "http" and scope.get("method", "GET") not in _SAFE_METHODS:
            if not self._is_allowed(scope):
                body = json.dumps(
                    {"detail": {"code": "cross_origin", "message": "Requête refusée : elle vient d'une page web d'une autre origine, ou d'un nom d'hôte inconnu (à déclarer dans BOBINE_ALLOWED_HOSTS)."}},
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

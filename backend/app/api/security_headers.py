"""En-têtes de sécurité posés sur toute réponse HTTP."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HOST_NAME = re.compile(r"[a-z0-9.-]+|[0-9a-f:.]+")
_POLICY = (
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "media-src 'self' data: blob:",
    "font-src 'self' data:",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'self'",
)


def socket_sources(host_header: str | None) -> str:
    """Adresses WebSocket du serveur joint, pour les navigateurs où `'self'` ne couvre pas `ws:`."""
    if not host_header:
        return ""
    try:
        parts = urlsplit(f"//{host_header}")
        port = parts.port
    except ValueError:
        return ""
    if not parts.hostname or not _HOST_NAME.fullmatch(parts.hostname):
        return ""
    name = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    netloc = f"{name}:{port}" if port else name
    return f" ws://{netloc} wss://{netloc}"


def content_security_policy(host_header: str | None) -> str:
    return "; ".join((*_POLICY, f"connect-src 'self'{socket_sources(host_header)}"))


class SecurityHeaders:
    """Ajoute CSP, `nosniff` et politique de référent aux réponses qui n'en portent pas."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        host = next((value.decode("latin-1") for key, value in scope.get("headers", ()) if key == b"host"), None)
        policy = content_security_policy(host)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("Content-Security-Policy", policy)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "same-origin")
            await send(message)

        await self.app(scope, receive, send_with_headers)

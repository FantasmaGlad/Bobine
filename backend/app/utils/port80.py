"""Accès sans numéro de port : `http://bobine.local` (port 80) renvoie vers le port réel de Bobine.

L'appliance le fait par une règle nftables posée par `install.sh`. Sur un poste de bureau, ce petit écouteur ne fait
que répondre une redirection ; il n'est ouvert que si le port 80 est libre et que le système permet de l'ouvrir
(Windows, macOS ; Linux réserve les ports inférieurs à 1024 à l'administrateur). Sinon rien ne change et les liens
affichés dans Réglages gardent le numéro de port. Redirection temporaire (307) : un changement de port de Bobine ne
doit pas rester mémorisé par les navigateurs.
"""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

REDIRECT_PORT = 80
_HEADER_LIMIT = 16 * 1024
_READ_TIMEOUT = 5.0

_server: asyncio.base_events.Server | None = None
_target_port: int | None = None


def is_active() -> bool:
    return _server is not None


def redirect_location(host_header: str, target: str, port: int) -> str:
    """Même hôte (sans son port), port de Bobine, même chemin et même requête."""
    try:
        hostname = urlsplit(f"//{host_header}").hostname or "bobine.local"
    except ValueError:
        hostname = "bobine.local"
    if ":" in hostname:
        hostname = f"[{hostname}]"
    path = target if target.startswith("/") else "/"
    return f"http://{hostname}:{port}{path}"


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=_READ_TIMEOUT)
        if len(head) > _HEADER_LIMIT:
            return
        lines = head.decode("latin-1").split("\r\n")
        parts = lines[0].split(" ")
        target = parts[1] if len(parts) >= 3 else "/"
        host = next((line.split(":", 1)[1].strip() for line in lines[1:] if line.lower().startswith("host:")), "")
        location = redirect_location(host, target, _target_port or 0)
        body = f'<a href="{location}">{location}</a>\n'.encode("utf-8")
        writer.write(
            b"HTTP/1.1 307 Temporary Redirect\r\n"
            + f"Location: {location}\r\n".encode("latin-1", "replace")
            + b"Content-Type: text/html; charset=utf-8\r\nCache-Control: no-store\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()
    except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
        pass
    finally:
        writer.close()


async def start(target_port: int) -> bool:
    """Ouvre l'écouteur du port 80 si c'est possible ; renvoie vrai s'il écoute."""
    global _server, _target_port
    if _server is not None or target_port == REDIRECT_PORT:
        return _server is not None
    _target_port = target_port
    try:
        _server = await asyncio.start_server(_handle, host="0.0.0.0", port=REDIRECT_PORT, limit=_HEADER_LIMIT)
    except OSError as exc:
        logger.info("Port 80 non disponible pour la redirection vers %s (%s) : les liens gardent le port.", target_port, exc)
        return False
    logger.info("Port 80 redirigé vers %s : http://bobine.local fonctionne sans numéro de port.", target_port)
    return True


async def stop() -> None:
    global _server
    server, _server = _server, None
    if server is not None:
        server.close()
        await server.wait_closed()

"""Compression HTTP (gzip) des réponses texte/JSON de l'API et du frontend statique.

Pourquoi : aucune compression n'existait. Mesuré sur la 5.0.2 : `frontend/out`
2,7 Mo de texte -> 0,76 Mo en gzip, JSON de `/api/radio/tracks` (5000 titres)
1,09 Mo -> 39 Ko. Les kiosques et télécommandes ouverts depuis un autre appareil
du réseau local (Wi-Fi) en profitent directement.

Ce qui n'est JAMAIS compressé (sinon la lecture ou la reprise casserait) :
- les flux média (`/stream`), les miniatures et le branding : binaires déjà
  compressés, servis avec Range/ETag par `app/utils/media_response.py` ;
- tout ce qui n'est pas du texte/JSON (audio, vidéo, images, ZIP) ;
- les requêtes `Range` et les réponses autres que 200 (206, 304...), déjà
  encodées, avec `Content-Disposition` (téléchargements) ou `ETag` (la
  compression changerait la représentation : le validateur d'origine ne serait
  plus exact) ;
- les WebSocket, les requêtes `HEAD` (longueur annoncée != longueur compressée) ;
- les clients bouclage (127.0.0.0/8, ::1) : le kiosque Chromium local et la WebView
  Android parlent à leur propre serveur sans réseau, la compression y coûterait
  du CPU pour aucun octet économisé.

Compatible Starlette 0.27 (profil Android, FastAPI 0.99) comme 1.x : seules les
API ASGI et `starlette.datastructures` de base sont utilisées.
"""

from __future__ import annotations

import ipaddress
import zlib
from typing import Any, Iterable

import anyio.to_thread
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Sous ce seuil le gzip ne rapporte rien (en-tête gzip + en-têtes HTTP en plus).
MIN_COMPRESSIBLE_SIZE = 1024
# `zlib` libère le GIL : au-delà de ce seuil, la compression part dans un thread
# pour ne pas bloquer la boucle d'évènements (tâches de lecture, WebSocket).
_THREAD_THRESHOLD = 32 * 1024
_COMPRESS_LEVEL = 5
# 16 + MAX_WBITS : conteneur gzip (et pas zlib brut).
_GZIP_WBITS = 31

_COMPRESSIBLE_TYPES = frozenset(
    {
        "application/json",
        "application/javascript",
        "application/xml",
        "application/manifest+json",
        "image/svg+xml",
    }
)


def accepts_gzip(accept_encoding: str | None) -> bool:
    """Vrai si `Accept-Encoding` autorise gzip (ou `*`) avec un q > 0."""
    if not accept_encoding:
        return False
    wildcard = False
    for part in accept_encoding.split(","):
        coding, _, params = part.strip().partition(";")
        coding = coding.strip().lower()
        if coding not in ("gzip", "x-gzip", "*"):
            continue
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name.strip().lower() == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        if coding == "*":
            wildcard = quality > 0
        else:
            return quality > 0  # gzip nommé : prioritaire sur `*`
    return wildcard


def is_compressible_media_type(content_type: str | None) -> bool:
    """Texte et formats structurés seulement (jamais audio/vidéo/image/ZIP)."""
    if not content_type:
        return False
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type == "text/event-stream":  # flux continu : la mise en tampon gzip le figerait
        return False
    return (
        media_type.startswith("text/")
        or media_type in _COMPRESSIBLE_TYPES
        or media_type.endswith("+json")
        or media_type.endswith("+xml")
    )


def is_loopback_client(scope: Scope) -> bool:
    client = scope.get("client")
    if not client:
        return False
    try:
        return ipaddress.ip_address(client[0]).is_loopback
    except ValueError:
        return False  # nom d'hôte (clients de test) : pas du bouclage


def request_allows_gzip(scope: Scope) -> bool:
    """Négociation côté requête, commune à l'API et au frontend statique."""
    headers = Headers(scope=scope)
    if headers.get("range") or scope.get("method", "GET").upper() == "HEAD":
        return False
    if is_loopback_client(scope):
        return False
    return accepts_gzip(headers.get("accept-encoding"))


def gzip_compress(data: bytes) -> bytes:
    compressor = zlib.compressobj(_COMPRESS_LEVEL, zlib.DEFLATED, _GZIP_WBITS)
    return compressor.compress(data) + compressor.flush()


def add_vary_accept_encoding(headers: MutableHeaders) -> None:
    existing = headers.get("vary")
    if not existing:
        headers["vary"] = "Accept-Encoding"
        return
    tokens = [token.strip().lower() for token in existing.split(",")]
    if "*" not in tokens and "accept-encoding" not in tokens:
        headers["vary"] = f"{existing}, Accept-Encoding"


class ApiCompressionMiddleware:
    """gzip des réponses JSON/texte de `/api/*`, uniquement quand le client le
    demande et que la réponse est une représentation complète sans validateur.
    Le frontend statique négocie lui-même (ETag par contenu, cf.
    `RevalidateStaticFiles` dans `app/main.py`)."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        path_prefix: str = "/api/",
        excluded_prefixes: Iterable[str] = ("/api/thumbnails/", "/api/branding/"),
        excluded_fragments: Iterable[str] = ("/stream",),
        minimum_size: int = MIN_COMPRESSIBLE_SIZE,
    ) -> None:
        self.app = app
        self.path_prefix = path_prefix
        self.excluded_prefixes = tuple(excluded_prefixes)
        self.excluded_fragments = tuple(excluded_fragments)
        self.minimum_size = minimum_size

    def _path_is_eligible(self, path: str) -> bool:
        if not path.startswith(self.path_prefix) or path.startswith(self.excluded_prefixes):
            return False
        return not any(fragment in path for fragment in self.excluded_fragments)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or not self._path_is_eligible(scope.get("path", ""))
            or not request_allows_gzip(scope)
        ):
            await self.app(scope, receive, send)
            return
        await _GzipResponder(self.app, self.minimum_size)(scope, receive, send)


class _GzipResponder:
    def __init__(self, app: ASGIApp, minimum_size: int) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.send: Send | None = None
        self.initial_message: Message = {}
        self.compressor: Any = None
        self.passthrough = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self._send_with_gzip)

    @staticmethod
    def _is_compressible_response(headers: Headers, status: int) -> bool:
        return (
            status == 200
            and is_compressible_media_type(headers.get("content-type"))
            and "content-encoding" not in headers
            and "content-range" not in headers
            and "content-disposition" not in headers
            and "etag" not in headers
        )

    async def _send_with_gzip(self, message: Message) -> None:
        assert self.send is not None
        message_type = message["type"]

        if message_type == "http.response.start":
            headers = Headers(raw=message["headers"])
            if not self._is_compressible_response(headers, message["status"]):
                self.passthrough = True
                await self.send(message)
                return
            # Mise en attente : la décision (taille) dépend du premier corps.
            self.initial_message = message
            return

        if message_type != "http.response.body" or self.passthrough:
            await self.send(message)
            return

        body: bytes = message.get("body", b"")
        more_body: bool = message.get("more_body", False)
        headers = MutableHeaders(raw=self.initial_message["headers"])

        if self.compressor is None:
            add_vary_accept_encoding(headers)
            if not more_body and len(body) < self.minimum_size:
                # Réponse complète trop petite : envoyée telle quelle.
                self.passthrough = True
                await self.send(self.initial_message)
                await self.send(message)
                return
            headers["content-encoding"] = "gzip"
            if not more_body:
                compressed = await self._compress_once(body)
                headers["content-length"] = str(len(compressed))
                await self.send(self.initial_message)
                await self.send({"type": "http.response.body", "body": compressed})
                return
            # Corps en plusieurs morceaux : longueur inconnue d'avance.
            if "content-length" in headers:
                del headers["content-length"]
            self.compressor = zlib.compressobj(_COMPRESS_LEVEL, zlib.DEFLATED, _GZIP_WBITS)
            await self.send(self.initial_message)

        chunk = self.compressor.compress(body)
        if not more_body:
            chunk += self.compressor.flush()
        await self.send({"type": "http.response.body", "body": chunk, "more_body": more_body})

    @staticmethod
    async def _compress_once(body: bytes) -> bytes:
        if len(body) >= _THREAD_THRESHOLD:
            return await anyio.to_thread.run_sync(gzip_compress, body)
        return gzip_compress(body)

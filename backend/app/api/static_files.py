"""Fichiers statiques servis par l'application : miniatures, logo personnalisé et frontend exporté."""

import hashlib
import logging
import platform
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers
from starlette.staticfiles import NotModifiedResponse

from app.config import settings
from app.utils import ui_language
from app.utils.android_runtime import is_android
from app.api.http_compression import (
    MIN_COMPRESSIBLE_SIZE,
    add_vary_accept_encoding,
    gzip_compress,
    is_compressible_media_type,
    request_allows_gzip,
)

logger = logging.getLogger(__name__)

_IS_ANDROID = is_android()


class _EnsuredDirStaticFiles(StaticFiles):

    async def check_config(self) -> None:
        try:
            Path(self.directory).mkdir(parents=True, exist_ok=True)
        except OSError:
            pass

        try:
            await super().check_config()
        except RuntimeError:
            self.config_checked = False
            raise

    async def __call__(self, scope, receive, send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except RuntimeError as exc:
            if scope.get("type") != "http" or "does not exist" not in str(exc):
                raise
            from starlette.responses import PlainTextResponse

            await PlainTextResponse("Introuvable", status_code=404)(scope, receive, send)


if _IS_ANDROID:
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend_out"
elif getattr(sys, "frozen", False):
    if platform.system() == "Darwin":
        frontend_out = Path(sys.executable).resolve().parent.parent / "Resources" / "frontend" / "out"
    else:
        frontend_out = Path(sys.executable).resolve().parent / "frontend" / "out"
else:
    frontend_out = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "out"


class RevalidateStaticFiles(StaticFiles):
    """StaticFiles standard, avec revalidation systématique des fichiers du frontend exporté (`frontend/out`)."""

    _GZIP_CACHE_MAX_BYTES = 8 * 1024 * 1024

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._gzip_cache: dict[tuple[str, str], bytes] = {}
        self._gzip_cache_bytes = 0

    def _gzipped(self, full_path, content_hash: str, data: bytes) -> bytes:
        key = (str(full_path), content_hash)
        compressed = self._gzip_cache.get(key)
        if compressed is None:
            compressed = gzip_compress(data)
            if self._gzip_cache_bytes + len(compressed) > self._GZIP_CACHE_MAX_BYTES:
                self._gzip_cache.clear()
                self._gzip_cache_bytes = 0
            self._gzip_cache[key] = compressed
            self._gzip_cache_bytes += len(compressed)
        return compressed

    async def get_response(self, path: str, scope):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Ressource d'API introuvable")
        return await super().get_response(path, scope)

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        request_headers = Headers(scope=scope)
        response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
        data: bytes | None = None
        content_hash = ""
        try:
            with open(full_path, "rb") as f:
                data = f.read()
            content_hash = hashlib.md5(data, usedforsecurity=False).hexdigest()
            response.headers["etag"] = f'"{content_hash}"'
        except OSError:
            pass
        identity_etag = response.headers["etag"]

        gzip_etag: str | None = None
        if is_compressible_media_type(response.headers.get("content-type")):
            add_vary_accept_encoding(response.headers)
            if data is not None and len(data) >= MIN_COMPRESSIBLE_SIZE and request_allows_gzip(scope):
                gzip_etag = f'"{content_hash}-gzip"'

        if_none_match = request_headers.get("if-none-match")
        if if_none_match:
            client_tags = {tag.strip().removeprefix("W/") for tag in if_none_match.split(",")}
            matched = next((tag for tag in (gzip_etag, identity_etag) if tag and tag in client_tags), None)
            if matched:
                response.headers["etag"] = matched
                response = NotModifiedResponse(response.headers)
                gzip_etag = None
        if gzip_etag is not None:
            headers = {
                name: value
                for name, value in response.headers.items()
                if name not in ("content-length", "etag", "accept-ranges")
            }
            headers["etag"] = gzip_etag
            headers["content-encoding"] = "gzip"
            response = Response(
                self._gzipped(full_path, content_hash, data),
                status_code=status_code,
                headers=headers,
            )
        response.headers["Cache-Control"] = "no-cache"
        return response


def mount_static_files(app: FastAPI) -> None:
    """Monte les dossiers statiques, le frontend en dernier : sa route générique masquerait les autres."""
    thumbnails_path = Path(settings.thumbnails_dir)
    thumbnails_path.mkdir(parents=True, exist_ok=True)
    app.mount("/api/thumbnails", _EnsuredDirStaticFiles(directory=str(thumbnails_path)), name="thumbnails")

    branding_path = Path(settings.branding_dir)
    branding_path.mkdir(parents=True, exist_ok=True)
    app.mount("/api/branding", StaticFiles(directory=str(branding_path)), name="branding")

    if frontend_out.exists():
        logger.info(f"Montage du frontend statique depuis {frontend_out}")
        app.mount("/", ui_language.LanguageFrontend(frontend_out, RevalidateStaticFiles), name="frontend")
    else:
        logger.warning("Dossier frontend/out introuvable. Le frontend ne sera pas servi par FastAPI (dev direct).")

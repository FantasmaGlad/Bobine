"""Réponses HTTP des flux média (vidéo, audio, pochettes, fonds) conformes à la RFC 9110, pour TOUS les navigateurs — Firefox compris."""

import asyncio
from email.utils import formatdate, parsedate_to_datetime
from pathlib import Path
from typing import Mapping

import aiofiles
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse

from app.utils.android_runtime import is_android

_IS_ANDROID = is_android()

_READ_BLOCK_SIZE = 1024 * 1024 if _IS_ANDROID else 8192 * 16


class RangeNotSatisfiable(Exception):
    """Début de plage au-delà de la fin du fichier (réponse 416)."""


def parse_byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Renvoie (début, fin) inclusifs, ou None pour servir le fichier entier (en-tête absent, d'une autre unité, multiple ou illisible — la RFC 9110 autorise à ignorer `Range`)."""
    if not header:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or not spec.strip() or "," in spec:
        return None
    first, dash, last = spec.strip().partition("-")
    if not dash:
        return None
    try:
        if first == "":
            suffix = int(last)
            if suffix <= 0:
                raise RangeNotSatisfiable
            if size == 0:
                raise RangeNotSatisfiable
            return max(0, size - suffix), size - 1
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start < 0 or (last and end < start):
        return None
    if start >= size:
        raise RangeNotSatisfiable
    return start, min(end, size - 1)


def _validators(stat) -> tuple[str, str]:
    etag = f'"{stat.st_size:x}-{stat.st_mtime_ns:x}"'
    return etag, formatdate(stat.st_mtime, usegmt=True)


def _if_range_matches(if_range: str | None, etag: str, last_modified: str) -> bool:
    if not if_range:
        return True
    candidate = if_range.strip()
    if candidate.startswith('"') or candidate.startswith("W/"):
        return candidate == etag
    try:
        return parsedate_to_datetime(candidate) == parsedate_to_datetime(last_modified)
    except (TypeError, ValueError):
        return False


async def build_media_response(
    file_path: Path,
    request_headers: Mapping[str, str],
    method: str,
    content_type: str,
) -> Response:
    """Sert `file_path` (GET ou HEAD) avec support complet de `Range`."""
    stat = None
    try:
        stat = await run_in_threadpool(file_path.stat)
    except OSError:
        raise HTTPException(status_code=404, detail="Fichier manquant sur le disque")

    size = stat.st_size
    etag, last_modified = _validators(stat)
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": content_type,
        "ETag": etag,
        "Last-Modified": last_modified,
        "X-Content-Type-Options": "nosniff",
    }

    range_header = request_headers.get("range")
    if not range_header:
        if_none_match = request_headers.get("if-none-match")
        if if_none_match and etag in (tag.strip() for tag in if_none_match.split(",")):
            return Response(status_code=304, headers={"ETag": etag, "Last-Modified": last_modified})

    byte_range = None
    if range_header and _if_range_matches(request_headers.get("if-range"), etag, last_modified):
        try:
            byte_range = parse_byte_range(range_header, size)
        except RangeNotSatisfiable:
            return Response(
                status_code=416,
                headers={**base_headers, "Content-Range": f"bytes */{size}", "Content-Length": "0"},
            )

    if byte_range is None:
        start, end, status = 0, size - 1, 200
    else:
        (start, end), status = byte_range, 206
    length = max(0, end - start + 1)

    headers = {**base_headers, "Content-Length": str(length)}
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"

    if method.upper() == "HEAD" or length == 0:
        return Response(status_code=status, headers=headers)

    async def body():
        handle = await aiofiles.open(file_path, "rb")
        try:
            await handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = await handle.read(min(_READ_BLOCK_SIZE, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
        except OSError:
            return
        finally:
            closing = asyncio.ensure_future(handle.close())
            try:
                await asyncio.shield(closing)
            except asyncio.CancelledError:
                pass
            except OSError:
                pass

    return StreamingResponse(body(), status_code=status, headers=headers)

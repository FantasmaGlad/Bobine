"""Réponse de flux à plages HTTP pour un fichier média, support externe débranché compris."""

from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import Response

from app.storage import availability as storage_availability
from app.storage.service import service as storage_service
from app.utils.media_response import build_media_response


def storage_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "storage_unavailable", "message": "Ce média est sur un support externe actuellement débranché : rebranchez-le ou importez le média."},
        headers={"Retry-After": "5"},
    )


async def range_stream_response(
    file_path: Path, request: Request, content_type: str, storage_id: int | None = None
) -> Response:
    if storage_id is None:
        return await build_media_response(file_path, request.headers, request.method, content_type)
    if not storage_availability.is_online(storage_id):
        raise storage_unavailable()
    storage_service.touch_storage(storage_id)
    try:
        return await build_media_response(file_path, request.headers, request.method, content_type)
    except HTTPException as exc:
        if exc.status_code == 404:
            storage_service.request_refresh()
            raise storage_unavailable() from exc
        raise

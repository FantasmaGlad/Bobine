"""Téléversement par morceaux reprenable — voir `app/utils/staged_uploads.py` pour le protocole et la justification."""

import logging
import time

import aiofiles
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.responses import UploadState
from app.utils import staged_uploads as staged

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(ge=0)
    fingerprint: str | None = Field(default=None, max_length=1024)


def _state(session: staged.Session) -> dict:
    offset = session.offset
    return {
        "upload_id": session.upload_id,
        "offset": offset,
        "size": session.size,
        "complete": offset == session.size,
        "chunk_size": staged.CHUNK_SIZE,
    }


@router.post("", status_code=201, response_model=UploadState)
def create_upload(payload: UploadCreate) -> dict:
    return _state(staged.create_session(payload.filename, payload.size, payload.fingerprint))


@router.get("/{upload_id}")
def get_upload(upload_id: str) -> dict:
    return _state(staged.get_session(upload_id))


def _declared_offset(upload_id: str, request: Request) -> int:
    try:
        return int(request.headers.get("upload-offset", ""))
    except ValueError:
        logger.warning("Upload %s : en-tête Upload-Offset manquant ou invalide", staged.short_id(upload_id))
        raise HTTPException(status_code=400, detail="En-tête Upload-Offset manquant ou invalide")


class _Received:
    def __init__(self) -> None:
        self.bytes = 0


async def _stream_into(path, request: Request, remaining: int, received: _Received) -> None:
    async with aiofiles.open(path, "ab") as f:
        async for chunk in request.stream():
            overflow = received.bytes + len(chunk) > remaining
            if overflow:
                chunk = chunk[: remaining - received.bytes]
            await f.write(chunk)
            received.bytes += len(chunk)
            if overflow:
                raise HTTPException(status_code=413, detail="Le morceau dépasse la taille annoncée du fichier")


async def _write_chunk(upload_id: str, request: Request, current: int, remaining: int) -> tuple[int, float]:
    received = _Received()
    started = time.monotonic()
    try:
        await _stream_into(staged._part_path(upload_id), request, remaining, received)
    except HTTPException:
        logger.warning("Upload %s : morceau refusé à l'offset %d (dépasse la taille annoncée)", staged.short_id(upload_id), current)
        raise
    except BaseException as exc:
        logger.warning(
            "Upload %s : morceau interrompu à l'offset %d après %d octets reçus en %.1f s (%s)",
            staged.short_id(upload_id), current, received.bytes, time.monotonic() - started, type(exc).__name__,
        )
        raise
    return received.bytes, time.monotonic() - started


def _log_received(upload_id: str, session: staged.Session, state: dict, written: int, elapsed: float) -> None:
    logger.info(
        "Upload %s : morceau reçu, %d octets en %.2f s (%.1f Mo/s), offset %d/%d",
        staged.short_id(upload_id), written, elapsed,
        (written / 1_048_576 / elapsed) if elapsed > 0 else 0.0, state["offset"], state["size"],
    )
    if state["complete"]:
        logger.info(
            "Upload %s : transfert complet, %d octets reçus en %.1f s depuis la création",
            staged.short_id(upload_id), state["size"], max(0.0, time.time() - session.created_at),
        )


@router.patch("/{upload_id}", response_model=UploadState)
async def append_chunk(upload_id: str, request: Request) -> JSONResponse:
    session = staged.get_session(upload_id)
    declared = _declared_offset(upload_id, request)
    staged.acquire(upload_id)
    try:
        current = session.offset
        if declared != current:
            logger.info(
                "Upload %s : reprise désynchronisée (client à %d, serveur à %d)",
                staged.short_id(upload_id), declared, current,
            )
            return JSONResponse(
                status_code=409,
                headers={"Upload-Offset": str(current)},
                content={"detail": "Décalage de reprise", "offset": current, "size": session.size},
            )
        written, elapsed = await _write_chunk(upload_id, request, current, session.size - current)
        state = _state(staged.get_session(upload_id))
        _log_received(upload_id, session, state, written, elapsed)
        return JSONResponse(status_code=200, headers={"Upload-Offset": str(state["offset"])}, content=state)
    finally:
        staged.release(upload_id)


@router.delete("/{upload_id}", status_code=204)
def cancel_upload(upload_id: str) -> None:
    staged.abort(upload_id)

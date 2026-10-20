"""Téléversement par morceaux reprenable — voir `app/utils/staged_uploads.py`
pour le protocole et la justification."""

import logging
import time

import aiofiles
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.utils import staged_uploads as staged

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=512)
    size: int = Field(ge=0)
    # Empreinte stable côté client (nom|taille|dernière modification) :
    # permet de reprendre le même fichier après un rechargement de page.
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


@router.post("", status_code=201)
def create_upload(payload: UploadCreate) -> dict:
    return _state(staged.create_session(payload.filename, payload.size, payload.fingerprint))


@router.get("/{upload_id}")
def get_upload(upload_id: str) -> dict:
    return _state(staged.get_session(upload_id))


@router.patch("/{upload_id}")
async def append_chunk(upload_id: str, request: Request) -> JSONResponse:
    session = staged.get_session(upload_id)
    try:
        declared = int(request.headers.get("upload-offset", ""))
    except ValueError:
        logger.warning("Upload %s : en-tête Upload-Offset manquant ou invalide", staged.short_id(upload_id))
        raise HTTPException(status_code=400, detail="En-tête Upload-Offset manquant ou invalide")

    staged.acquire(upload_id)
    try:
        current = session.offset
        if declared != current:
            # Le client est désynchronisé (réponse perdue, reprise) : on lui
            # donne l'offset réel, c'est lui qui repart de là.
            logger.info(
                "Upload %s : reprise désynchronisée (client à %d, serveur à %d)",
                staged.short_id(upload_id), declared, current,
            )
            return JSONResponse(
                status_code=409,
                headers={"Upload-Offset": str(current)},
                content={"detail": "Décalage de reprise", "offset": current, "size": session.size},
            )
        remaining = session.size - current
        written = 0
        started = time.monotonic()
        try:
            async with aiofiles.open(staged._part_path(upload_id), "ab") as f:
                async for chunk in request.stream():
                    if written + len(chunk) > remaining:
                        chunk = chunk[: remaining - written]
                        overflow = True
                    else:
                        overflow = False
                    await f.write(chunk)
                    written += len(chunk)
                    if overflow:
                        raise HTTPException(status_code=413, detail="Le morceau dépasse la taille annoncée du fichier")
        except HTTPException:
            logger.warning("Upload %s : morceau refusé à l'offset %d (dépasse la taille annoncée)", staged.short_id(upload_id), current)
            raise
        except BaseException as exc:
            # Connexion coupée par le client (onglet fermé, Wi-Fi), disque plein,
            # annulation : les octets déjà écrits restent et la reprise repartira
            # de l'offset réel. C'est le journal qui permet de le constater.
            logger.warning(
                "Upload %s : morceau interrompu à l'offset %d après %d octets reçus en %.1f s (%s)",
                staged.short_id(upload_id), current, written, time.monotonic() - started, type(exc).__name__,
            )
            raise
        elapsed = time.monotonic() - started
        state = _state(staged.get_session(upload_id))
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
        return JSONResponse(status_code=200, headers={"Upload-Offset": str(state["offset"])}, content=state)
    finally:
        staged.release(upload_id)


@router.delete("/{upload_id}", status_code=204)
def cancel_upload(upload_id: str) -> None:
    staged.abort(upload_id)

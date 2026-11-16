"""Routes des sorties audio."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.contract import AUDIO_TEST_CHANNELS
from app.database import get_db
from app.devices.audio_meta import load_audio_meta, update_audio_meta, with_listing_meta, with_meta
from app.devices.base import DeviceError
from app.devices.service import service

from .access import Access, fail, guard, log, require_access

router = APIRouter()


class AudioDefaultRequest(BaseModel):
    id: str


class AudioVolumeRequest(BaseModel):
    id: str
    volume: float | None = None
    muted: bool | None = None


class AudioBalanceRequest(BaseModel):
    id: str
    balance: float


class AudioToneRequest(BaseModel):
    id: str
    channel: str


class AudioProfileRequest(BaseModel):
    id: str
    index: int


class AudioMetaRequest(BaseModel):
    id: str
    alias: str | None = None
    hidden: bool | None = None


@router.get("/audio")
async def audio_list(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    return with_listing_meta(await guard(service.driver.audio_list()), db)


@router.get("/audio/details")
async def audio_details(id: str, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    details = await guard(service.driver.audio_details(id))
    return with_meta(details, load_audio_meta(db)) if details.get("supported") else details


@router.post("/audio/balance")
async def audio_balance(payload: AudioBalanceRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if not (-1.0 <= payload.balance <= 1.0):
        raise fail(400, "bad_balance", "La balance doit être comprise entre -1 et 1.")
    await guard(service.driver.audio_set_balance(payload.id, payload.balance))
    return {"ok": True}


@router.post("/audio/test")
async def audio_test(payload: AudioToneRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if payload.channel not in AUDIO_TEST_CHANNELS:
        raise fail(400, "bad_channel", "Canal de test inconnu.")
    await guard(service.driver.audio_test_tone(payload.id, payload.channel))
    return {"ok": True}


@router.post("/audio/profile")
async def audio_profile(payload: AudioProfileRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.audio_set_profile(payload.id, payload.index))
    return {"ok": True}


@router.put("/audio/meta")
def audio_meta(payload: AudioMetaRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Nom personnalisé et masquage d'une sortie : réglages de Bobine, communs à toutes les plateformes."""
    try:
        entry = update_audio_meta(db, payload.id, payload.alias, payload.hidden)
    except DeviceError as exc:
        raise fail(exc.status, exc.code, exc.message) from exc
    return {"ok": True, "alias": entry.get("alias"), "hidden": bool(entry.get("hidden"))}


@router.post("/audio/default")
async def audio_set_default(payload: AudioDefaultRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await guard(service.driver.audio_set_default(payload.id))
    log(db, "devices_audio_default", payload.id[:80])
    return {"ok": True}


@router.post("/audio/volume")
async def audio_set_volume(payload: AudioVolumeRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if payload.volume is not None and not (0.0 <= payload.volume <= 1.5):
        raise fail(400, "bad_volume", "Le volume doit être compris entre 0 et 1,5.")
    await guard(service.driver.audio_set_volume(payload.id, payload.volume, payload.muted))
    return {"ok": True}

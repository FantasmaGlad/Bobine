"""Routes des sorties radio : carte, routage audio et mixage."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices.mixer import apply_mixer, mixer_view
from app.devices.routing_view import apply_route, routing_view
from app.devices.service import service
from app.devices.topology_view import topology_view

from .access import Access, guard, log, require_access

router = APIRouter()


class RoutingRequest(BaseModel):
    channel: str
    sink_id: str | None = None
    fallback: str | None = None
    clear: bool = False


class MixerRequest(BaseModel):
    mix: dict | None = None
    sound: dict | None = None


@router.get("/topology")
async def topology(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Graphe machine → sorties audio, Bluetooth, Wi-Fi, Ethernet, écrans et télécommandes Bobine."""
    return await topology_view(service, db)


@router.get("/routing")
async def get_routing(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await guard(routing_view(service, db))


@router.put("/routing")
async def set_routing(payload: RoutingRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Choisit (ou efface) la sortie audio d'une sortie radio, ou change son repli quand la sortie est absente."""
    detail = await guard(apply_route(service, db, payload.channel, payload.sink_id, payload.fallback, payload.clear))
    log(db, "devices_audio_route", detail[:120])
    await service.reconcile_routes()
    service.notify("routing")
    return await guard(routing_view(service, db))


@router.get("/mixer")
async def get_mixer(_: Access = Depends(require_access)) -> dict[str, Any]:
    return mixer_view()


@router.put("/mixer/{channel}")
async def set_mixer(channel: str, payload: MixerRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Modifie le mixage et/ou l'égaliseur de la musique d'une sortie radio."""
    await guard(apply_mixer(db, channel, payload.mix, payload.sound))
    return mixer_view()

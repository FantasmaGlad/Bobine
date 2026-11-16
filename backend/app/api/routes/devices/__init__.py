"""API « Périphériques » : audio, Bluetooth, Wi-Fi et sorties radio (moteurs dans app/devices/)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.devices.service import WIFI_CONFIRM_SECONDS, service
from app.utils.deployment import get_deployment_profile

from . import audio, bluetooth, radio, wifi
from .access import Access, fail, guard, is_local_request, require_access

router = APIRouter(prefix="/api/devices", tags=["devices"])


class SystemSettingsRequest(BaseModel):
    target: str


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    return {
        "local": is_local_request(request),
        "platform": get_deployment_profile(),
        "driver": service.driver.name,
        "wifi_confirm_seconds": WIFI_CONFIRM_SECONDS,
        "capabilities": await guard(service.driver.capabilities()),
    }


@router.post("/system-settings")
async def open_system_settings(payload: SystemSettingsRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    """Ouvre l'écran de réglages correspondant SUR la machine (pour l'écran local ou la télécommande)."""
    if payload.target not in ("wifi", "bluetooth", "sound"):
        raise fail(400, "bad_target", "Réglage inconnu.")
    await guard(service.driver.open_system_settings(payload.target))
    return {"ok": True}


for module in (audio, bluetooth, wifi, radio):
    router.include_router(module.router)

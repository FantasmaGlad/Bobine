"""Routes du Wi-Fi : tout changement qui peut couper le client est confirmé, puis annulé faute de reconfirmation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices.service import service
from app.devices.wifi_guard import require_ack

from .access import Access, fail, guard, log, require_access

router = APIRouter()


class WifiConnectRequest(BaseModel):
    ssid: str
    password: str | None = None
    acknowledge_disconnect: bool = False


class WifiForgetRequest(BaseModel):
    ssid: str
    acknowledge_disconnect: bool = False


class WifiPowerRequest(BaseModel):
    on: bool
    acknowledge_disconnect: bool = False


@router.get("/wifi")
async def wifi_status(_: Access = Depends(require_access)) -> dict[str, Any]:
    status = await guard(service.driver.wifi_status())
    status["pending_change"] = service.wifi_pending_info()
    return status


@router.post("/wifi/scan")
async def wifi_scan(_: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.wifi_scan())
    return {"ok": True}


@router.post("/wifi/power")
async def wifi_power(payload: WifiPowerRequest, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not payload.on:
        await guard(require_ack(service, access.local, access.ip, payload.acknowledge_disconnect))
    await guard(service.driver.wifi_set_power(payload.on))
    if not payload.on:
        service.arm_wifi_rollback("power_off", None, "Wi-Fi")
    log(db, "devices_wifi_power", "on" if payload.on else "off")
    return {"ok": True, "pending_change": service.wifi_pending_info()}


@router.post("/wifi/connect")
async def wifi_connect(payload: WifiConnectRequest, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    ssid = payload.ssid.strip()
    if not ssid:
        raise fail(400, "bad_ssid", "Nom de réseau manquant.")
    if payload.password and not access.local:
        raise fail(403, "password_local_only", "Le mot de passe Wi-Fi ne peut être saisi que sur l'écran local de la machine. À distance, seuls les réseaux déjà enregistrés ou ouverts sont proposés.")
    if service.wifi_pending is not None:
        raise fail(409, "change_pending", "Un changement de Wi-Fi attend sa confirmation.")
    await guard(require_ack(service, access.local, access.ip, payload.acknowledge_disconnect))
    previous = await guard(service.driver.wifi_current_connection())
    await guard(service.driver.wifi_connect(ssid, payload.password))
    service.arm_wifi_rollback("connect", previous, ssid)
    log(db, "devices_wifi_connect", ssid[:80])
    return {"ok": True, "pending_change": service.wifi_pending_info()}


@router.post("/wifi/confirm")
async def wifi_confirm(_: Access = Depends(require_access)) -> dict[str, bool]:
    return {"confirmed": service.confirm_wifi_change()}


@router.post("/wifi/forget")
async def wifi_forget(payload: WifiForgetRequest, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    current = await guard(service.driver.wifi_current_connection())
    if current and current == payload.ssid:
        await guard(require_ack(service, access.local, access.ip, payload.acknowledge_disconnect))
    await guard(service.driver.wifi_forget(payload.ssid))
    log(db, "devices_wifi_forget", payload.ssid[:80])
    return {"ok": True}

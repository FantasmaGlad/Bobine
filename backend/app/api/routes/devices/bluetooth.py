"""Routes du Bluetooth."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices.service import service

from .access import Access, guard, log, require_access

router = APIRouter()


class BluetoothPowerRequest(BaseModel):
    on: bool


class BluetoothAddressRequest(BaseModel):
    address: str


class BluetoothPairingResponse(BaseModel):
    address: str
    accept: bool


@router.get("/bluetooth")
async def bluetooth_status(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await guard(service.driver.bluetooth_status())


@router.post("/bluetooth/permission")
async def bluetooth_permission(_: Access = Depends(require_access)) -> dict[str, bool]:
    """Android : affiche sur l'appareil la demande d'autorisation « Appareils à proximité »."""
    await guard(service.driver.bluetooth_request_permission())
    return {"ok": True}


@router.post("/bluetooth/power")
async def bluetooth_power(payload: BluetoothPowerRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_set_power(payload.on))
    log(db, "devices_bluetooth_power", "on" if payload.on else "off")
    return {"ok": True}


@router.post("/bluetooth/scan")
async def bluetooth_scan(payload: BluetoothPowerRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_scan(payload.on))
    return {"ok": True}


@router.post("/bluetooth/pair")
async def bluetooth_pair(payload: BluetoothAddressRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_pair(payload.address))
    log(db, "devices_bluetooth_pair", payload.address)
    return {"ok": True}


@router.post("/bluetooth/pairing/respond")
async def bluetooth_pairing_respond(payload: BluetoothPairingResponse, _: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_respond_pairing(payload.address, payload.accept))
    return {"ok": True}


@router.post("/bluetooth/connect")
async def bluetooth_connect(payload: BluetoothAddressRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_connect(payload.address))
    return {"ok": True}


@router.post("/bluetooth/disconnect")
async def bluetooth_disconnect(payload: BluetoothAddressRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_disconnect(payload.address))
    return {"ok": True}


@router.post("/bluetooth/forget")
async def bluetooth_forget(payload: BluetoothAddressRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await guard(service.driver.bluetooth_forget(payload.address))
    log(db, "devices_bluetooth_forget", payload.address)
    return {"ok": True}

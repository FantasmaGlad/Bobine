"""API « Périphériques » : audio, Bluetooth, Wi-Fi (voir app/devices/).

Contrôle d'accès (app/devices/security.py) : fonction désactivée par défaut ; l'écran local est de
confiance, tout autre appareil doit présenter un code PIN d'administration (session par cookie).
Aucune erreur d'OS ne devient une 500 : `DeviceError` et toute exception inattendue sont convertis
en réponse JSON structurée `{"detail": {"code", "message"}}`.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices import security
from app.devices.base import DeviceError
from app.devices.service import WIFI_CONFIRM_SECONDS, service
from app.models import Setting
from app.utils.activity_log import log_activity
from app.utils.deployment import get_deployment_profile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Réglages et accès
# ---------------------------------------------------------------------------


def _get_setting(db: Session, key: str) -> str | None:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else None


def _set_setting(db: Session, key: str, value: str | None) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def is_local_request(request: Request) -> bool:
    """Requête venant de la machine elle-même (écran physique). Les en-têtes X-Forwarded-* sont ignorés."""
    return security.is_local_client(_client_ip(request))


def _fail(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


@dataclass
class Access:
    local: bool
    ip: str


def require_access(request: Request, db: Session = Depends(get_db)) -> Access:
    if _get_setting(db, security.SETTING_ENABLED) != "true":
        raise _fail(403, "devices_disabled", "La gestion des périphériques est désactivée. Activez-la depuis l'écran local.")
    ip = _client_ip(request)
    if is_local_request(request):
        return Access(local=True, ip=ip)
    if not _get_setting(db, security.SETTING_PIN_HASH):
        raise _fail(403, "pin_not_set", "Définissez d'abord un code PIN depuis l'écran local de la machine pour accéder aux périphériques à distance.")
    if not security.sessions.validate(request.cookies.get(security.SESSION_COOKIE), ip):
        raise _fail(401, "pin_required", "Saisissez le code PIN pour accéder aux périphériques.")
    return Access(local=False, ip=ip)


def require_local(request: Request) -> None:
    if not is_local_request(request):
        raise _fail(403, "local_only", "Cette opération n'est possible que depuis l'écran local de la machine.")


async def _guard(coro: Awaitable[T]) -> T:
    """Convertit toute erreur d'OS en réponse structurée ; jamais de 500."""
    try:
        return await coro
    except DeviceError as exc:
        raise _fail(exc.status, exc.code, exc.message) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Erreur inattendue du pilote de périphériques : %s", exc, exc_info=True)
        raise _fail(502, "driver_error", "Le système n'a pas pu exécuter cette opération.") from exc


def _log(db: Session, event: str, detail: str | None = None) -> None:
    log_activity(db, event, detail)


# ---------------------------------------------------------------------------
# État public, activation, PIN, session
# ---------------------------------------------------------------------------


class EnableRequest(BaseModel):
    enabled: bool


class PinRequest(BaseModel):
    pin: str


@router.get("/status")
async def get_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    enabled = _get_setting(db, security.SETTING_ENABLED) == "true"
    pin_set = bool(_get_setting(db, security.SETTING_PIN_HASH))
    local = is_local_request(request)
    authenticated = local or (pin_set and security.sessions.validate(request.cookies.get(security.SESSION_COOKIE), _client_ip(request)))
    if not enabled:
        access = "disabled"
    elif authenticated:
        access = "granted"
    elif not pin_set:
        access = "pin_not_set"
    else:
        access = "pin_required"
    result: dict[str, Any] = {
        "enabled": enabled,
        "pin_set": pin_set,
        "pin_length": security.PIN_LENGTH,
        "local": local,
        "access": access,
        "platform": get_deployment_profile(),
        "driver": service.driver.name,
        "session_minutes": int(security.SESSION_TTL_SECONDS // 60),
        "wifi_confirm_seconds": WIFI_CONFIRM_SECONDS,
    }
    if access == "granted":
        result["capabilities"] = await _guard(service.driver.capabilities())
    elif access == "pin_required":
        retry = security.rate_limiter.retry_after(_client_ip(request))
        if retry:
            result["retry_after"] = retry
    return result


@router.post("/admin/enable")
def set_enabled(payload: EnableRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_local(request)
    _set_setting(db, security.SETTING_ENABLED, "true" if payload.enabled else "false")
    if not payload.enabled:
        security.sessions.revoke_all()
    _log(db, "devices_enabled" if payload.enabled else "devices_disabled", None)
    return {"enabled": payload.enabled}


@router.post("/admin/pin")
def set_pin(payload: PinRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Définit ou remplace le PIN — uniquement depuis l'écran local (présence physique, sans ancien PIN)."""
    require_local(request)
    if not security.is_valid_pin(payload.pin):
        raise _fail(400, "bad_pin", f"Le code PIN doit comporter exactement {security.PIN_LENGTH} chiffres.")
    _set_setting(db, security.SETTING_PIN_HASH, security.hash_pin(payload.pin))
    security.sessions.revoke_all()
    _log(db, "devices_pin_set", None)  # jamais la valeur
    return {"pin_set": True}


@router.delete("/admin/pin")
def clear_pin(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    require_local(request)
    _set_setting(db, security.SETTING_PIN_HASH, None)
    security.sessions.revoke_all()
    _log(db, "devices_pin_cleared", None)
    return {"pin_set": False}


@router.post("/session")
def open_session(payload: PinRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, Any]:
    if _get_setting(db, security.SETTING_ENABLED) != "true":
        raise _fail(403, "devices_disabled", "La gestion des périphériques est désactivée.")
    stored = _get_setting(db, security.SETTING_PIN_HASH)
    if not stored:
        raise _fail(403, "pin_not_set", "Aucun code PIN n'est défini : définissez-en un depuis l'écran local.")
    ip = _client_ip(request)
    retry = security.rate_limiter.retry_after(ip)
    if retry:
        raise HTTPException(
            status_code=429,
            detail={"code": "locked", "message": f"Trop d'essais. Réessayez dans {retry} s.", "retry_after": retry},
            headers={"Retry-After": str(retry)},
        )
    if not security.verify_pin(payload.pin, stored):
        lockout = security.rate_limiter.register_failure(ip)
        _log(db, "devices_login_failed", f"IP {ip}")
        if lockout:
            _log(db, "devices_login_locked", f"IP {ip} bloquée {lockout} s")
            raise HTTPException(
                status_code=429,
                detail={"code": "locked", "message": f"Trop d'essais. Réessayez dans {lockout} s.", "retry_after": lockout},
                headers={"Retry-After": str(lockout)},
            )
        raise _fail(401, "bad_pin", "Code PIN incorrect.", attempts_left=security.rate_limiter.attempts_left(ip))
    security.rate_limiter.register_success(ip)
    token = security.sessions.create(ip)
    response.set_cookie(
        security.SESSION_COOKIE,
        token,
        max_age=int(security.SESSION_TTL_SECONDS),
        httponly=True,
        samesite="strict",
        path="/api/devices",
    )
    _log(db, "devices_login_ok", f"IP {ip}")
    return {"ok": True, "session_minutes": int(security.SESSION_TTL_SECONDS // 60)}


@router.delete("/session")
def close_session(request: Request, response: Response) -> dict[str, bool]:
    security.sessions.revoke(request.cookies.get(security.SESSION_COOKIE))
    response.delete_cookie(security.SESSION_COOKIE, path="/api/devices")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


class AudioDefaultRequest(BaseModel):
    id: str


class AudioVolumeRequest(BaseModel):
    id: str
    volume: float | None = None
    muted: bool | None = None


@router.get("/audio")
async def audio_list(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.driver.audio_list())


@router.post("/audio/default")
async def audio_set_default(payload: AudioDefaultRequest, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await _guard(service.driver.audio_set_default(payload.id))
    _log(db, "devices_audio_default", payload.id[:80])
    return {"ok": True}


@router.post("/audio/volume")
async def audio_set_volume(payload: AudioVolumeRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if payload.volume is not None and not (0.0 <= payload.volume <= 1.5):
        raise _fail(400, "bad_volume", "Le volume doit être compris entre 0 et 1,5.")
    await _guard(service.driver.audio_set_volume(payload.id, payload.volume, payload.muted))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bluetooth
# ---------------------------------------------------------------------------


class BluetoothPowerRequest(BaseModel):
    on: bool


class BluetoothAddressRequest(BaseModel):
    address: str


class BluetoothPairingResponse(BaseModel):
    address: str
    accept: bool


@router.get("/bluetooth")
async def bluetooth_status(_: Access = Depends(require_access)) -> dict[str, Any]:
    return await _guard(service.driver.bluetooth_status())


@router.post("/bluetooth/power")
async def bluetooth_power(payload: BluetoothPowerRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_set_power(payload.on))
    _log(db, "devices_bluetooth_power", "on" if payload.on else "off")
    return {"ok": True}


@router.post("/bluetooth/scan")
async def bluetooth_scan(payload: BluetoothPowerRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_scan(payload.on))
    return {"ok": True}


@router.post("/bluetooth/pair")
async def bluetooth_pair(payload: BluetoothAddressRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_pair(payload.address))
    _log(db, "devices_bluetooth_pair", payload.address)
    return {"ok": True}


@router.post("/bluetooth/pairing/respond")
async def bluetooth_pairing_respond(payload: BluetoothPairingResponse, _: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_respond_pairing(payload.address, payload.accept))
    return {"ok": True}


@router.post("/bluetooth/connect")
async def bluetooth_connect(payload: BluetoothAddressRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_connect(payload.address))
    return {"ok": True}


@router.post("/bluetooth/disconnect")
async def bluetooth_disconnect(payload: BluetoothAddressRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_disconnect(payload.address))
    return {"ok": True}


@router.post("/bluetooth/forget")
async def bluetooth_forget(payload: BluetoothAddressRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    await _guard(service.driver.bluetooth_forget(payload.address))
    _log(db, "devices_bluetooth_forget", payload.address)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Wi-Fi (avec filet de sécurité : confirmation + retour automatique après 60 s)
# ---------------------------------------------------------------------------


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


async def _reached_via_wifi(request: Request, access: Access) -> bool:
    """Vrai si l'appareil qui agit est sur le sous-réseau du Wi-Fi de la machine (il risque de perdre la main)."""
    if access.local:
        return False
    subnet = await service.driver.wifi_interface_subnet()
    if not subnet:
        return False
    try:
        return ipaddress.ip_address(security._normalize_ip(access.ip) or access.ip) in ipaddress.ip_network(subnet)
    except ValueError:
        return False


async def _require_ack(request: Request, access: Access, acknowledged: bool) -> None:
    if not acknowledged and await _guard(_reached_via_wifi(request, access)):
        raise _fail(
            409,
            "ack_required",
            "Vous êtes connecté à Bobine par ce réseau Wi-Fi : la modification peut couper cet accès. Confirmez pour continuer ; sans reconfirmation sous 60 s, l'ancien réseau sera rétabli.",
        )


@router.get("/wifi")
async def wifi_status(_: Access = Depends(require_access)) -> dict[str, Any]:
    status = await _guard(service.driver.wifi_status())
    status["pending_change"] = service.wifi_pending_info()
    return status


@router.post("/wifi/scan")
async def wifi_scan(_: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.wifi_scan())
    return {"ok": True}


@router.post("/wifi/power")
async def wifi_power(payload: WifiPowerRequest, request: Request, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    if not payload.on:
        await _require_ack(request, access, payload.acknowledge_disconnect)
    await _guard(service.driver.wifi_set_power(payload.on))
    if not payload.on:
        service.arm_wifi_rollback("power_off", None, "Wi-Fi")
    _log(db, "devices_wifi_power", "on" if payload.on else "off")
    return {"ok": True, "pending_change": service.wifi_pending_info()}


@router.post("/wifi/connect")
async def wifi_connect(payload: WifiConnectRequest, request: Request, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    ssid = payload.ssid.strip()
    if not ssid:
        raise _fail(400, "bad_ssid", "Nom de réseau manquant.")
    if payload.password and not access.local:
        # Le mot de passe ne se saisit que sur l'écran local (le réseau local est en HTTP).
        raise _fail(403, "password_local_only", "Le mot de passe Wi-Fi ne peut être saisi que sur l'écran local de la machine. À distance, seuls les réseaux déjà enregistrés ou ouverts sont proposés.")
    if service.wifi_pending is not None:
        raise _fail(409, "change_pending", "Un changement de Wi-Fi attend sa confirmation.")
    await _require_ack(request, access, payload.acknowledge_disconnect)
    previous = await _guard(service.driver.wifi_current_connection())
    await _guard(service.driver.wifi_connect(ssid, payload.password))
    service.arm_wifi_rollback("connect", previous, ssid)
    _log(db, "devices_wifi_connect", ssid[:80])  # jamais le mot de passe
    return {"ok": True, "pending_change": service.wifi_pending_info()}


@router.post("/wifi/confirm")
async def wifi_confirm(_: Access = Depends(require_access)) -> dict[str, bool]:
    return {"confirmed": service.confirm_wifi_change()}


@router.post("/wifi/forget")
async def wifi_forget(payload: WifiForgetRequest, request: Request, access: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, bool]:
    current = await _guard(service.driver.wifi_current_connection())
    if current and current == payload.ssid:
        await _require_ack(request, access, payload.acknowledge_disconnect)
    await _guard(service.driver.wifi_forget(payload.ssid))
    _log(db, "devices_wifi_forget", payload.ssid[:80])
    return {"ok": True}

"""API « Périphériques » : audio, Bluetooth, Wi-Fi (voir app/devices/).

Contrôle d'accès (app/devices/security.py) : fonction désactivée par défaut ; l'écran local est de
confiance, tout autre appareil doit présenter un code PIN d'administration (session par cookie).
Aucune erreur d'OS ne devient une 500 : `DeviceError` et toute exception inattendue sont convertis
en réponse JSON structurée `{"detail": {"code", "message"}}`.
"""

from __future__ import annotations

import ipaddress
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.devices import security
from app.devices.base import DeviceError
from app.devices.routing import FALLBACKS, describe_sink, load_routes, resolve_route, save_routes
from app.devices.service import WIFI_CONFIRM_SECONDS, service
from app.models import Setting
from app.radio_manager import RADIO_CHANNELS, get_all_radio_managers, get_radio_manager
from app.utils.activity_log import log_activity
from app.utils.deployment import get_deployment_profile
from app.utils.radio_mix import sanitize_mix, save_mix
from app.utils.radio_sound import sanitize_sound, save_sound
from app.utils.ws_manager import manager as ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])

T = TypeVar("T")

# Préfixes d'API qui partagent la session PIN : périphériques et stockage externe (app/routers/storage.py).
SESSION_COOKIES = (
    (security.SESSION_COOKIE, "/api/devices"),
    (security.STORAGE_SESSION_COOKIE, "/api/storage"),
)


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


def _locked(seconds: int) -> HTTPException:
    """429 « trop d'essais » (même forme pour le PIN et le code d'association)."""
    return HTTPException(
        status_code=429,
        detail={"code": "locked", "message": f"Trop d'essais. Réessayez dans {seconds} s.", "retry_after": seconds},
        headers={"Retry-After": str(seconds)},
    )


def _grant_session(response: Response, ip: str) -> None:
    """Ouvre une session d'administration et pose son cookie."""
    token = security.sessions.create(ip)
    # Même session, un cookie par préfixe d'API protégé par le même PIN : le navigateur n'envoie un cookie qu'à son
    # chemin, et deux cookies de même nom se gêneraient (le stockage externe a donc le sien, de même valeur).
    for name, path in SESSION_COOKIES:
        response.set_cookie(
            name,
            token,
            max_age=int(security.SESSION_TTL_SECONDS),
            httponly=True,
            samesite="strict",
            path=path,
        )


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
    token = request.cookies.get(security.SESSION_COOKIE) or request.cookies.get(security.STORAGE_SESSION_COOKIE)
    if not security.sessions.validate(token, ip):
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


class PairingClaimRequest(BaseModel):
    code: str
    pin: str


class PairingVerifyRequest(BaseModel):
    code: str


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


@router.get("/pairing/status")
def get_pairing_status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """État de l'appairage, sans effet de bord. Le code n'est renvoyé qu'à l'écran local."""
    pin_set = bool(_get_setting(db, security.SETTING_PIN_HASH))
    current = security.pairing_store.peek() if not pin_set else None
    local = is_local_request(request)
    return {
        "pin_set": pin_set,
        "code_length": security.PAIRING_CODE_LENGTH,
        "code": current[0] if current and local else None,
        "seconds_left": current[1] if current else 0,
    }


@router.post("/pairing/generate")
def generate_pairing_code(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Émet (ou renouvelle) le code d'association. Écran local uniquement ; inutile une fois le PIN défini."""
    require_local(request)
    if _get_setting(db, security.SETTING_PIN_HASH):
        raise _fail(409, "pin_already_set", "Un code PIN existe déjà : modifiez-le depuis l'écran local.")
    code = security.pairing_store.generate()
    return {"code": code, "seconds_left": security.PAIRING_CODE_TTL_SECONDS}


@router.post("/pairing/verify")
def verify_pairing_code(payload: PairingVerifyRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Dit tout de suite si le code saisi est le bon, sans le consommer (le PIN se choisit ensuite).

    Mêmes limites que l'usage : échecs comptés par IP et contre le code lui-même, donc pas de moyen plus rapide
    de deviner le code qu'avec /pairing/claim."""
    ip = _client_ip(request)
    retry = security.rate_limiter.retry_after(ip)
    if retry:
        raise _locked(retry)
    if _get_setting(db, security.SETTING_PIN_HASH):
        raise _fail(409, "pin_already_set", "Un code PIN existe déjà : modifiez-le depuis l'écran local.")
    if not security.pairing_store.check(payload.code):
        lockout = security.rate_limiter.register_failure(ip)
        _log(db, "devices_pairing_failed", f"IP {ip}")
        if lockout:
            raise _locked(lockout)
        raise _fail(401, "bad_pairing_code", "Code d'association incorrect ou expiré. Vérifiez l'écran de la machine.")
    return {"ok": True}


@router.post("/pairing/claim")
def claim_pairing_code(
    payload: PairingClaimRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Définit le PIN et active la fonction depuis un appareil distant, sur preuve du code affiché sur l'écran local.

    Réservé à la première configuration : un PIN existant ne peut être remplacé que depuis l'écran local."""
    ip = _client_ip(request)
    retry = security.rate_limiter.retry_after(ip)
    if retry:
        raise _locked(retry)
    if _get_setting(db, security.SETTING_PIN_HASH):
        raise _fail(409, "pin_already_set", "Un code PIN existe déjà : modifiez-le depuis l'écran local.")
    if not security.is_valid_pin(payload.pin):
        raise _fail(400, "bad_pin", f"Le code PIN doit comporter exactement {security.PIN_LENGTH} chiffres.")
    if not security.pairing_store.verify_and_consume(payload.code):
        lockout = security.rate_limiter.register_failure(ip)
        _log(db, "devices_pairing_failed", f"IP {ip}")
        if lockout:
            raise _locked(lockout)
        raise _fail(401, "bad_pairing_code", "Code d'association incorrect ou expiré. Vérifiez l'écran de la machine.")
    security.rate_limiter.register_success(ip)
    _set_setting(db, security.SETTING_PIN_HASH, security.hash_pin(payload.pin))
    _set_setting(db, security.SETTING_ENABLED, "true")
    _grant_session(response, ip)
    _log(db, "devices_paired_with_code", f"IP {ip}")
    return {"ok": True, "pin_set": True, "enabled": True, "session_minutes": int(security.SESSION_TTL_SECONDS // 60)}


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
    security.pairing_store.clear()  # le code n'a plus d'objet une fois le PIN défini
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
        raise _locked(retry)
    if not security.verify_pin(payload.pin, stored):
        lockout = security.rate_limiter.register_failure(ip)
        _log(db, "devices_login_failed", f"IP {ip}")
        if lockout:
            _log(db, "devices_login_locked", f"IP {ip} bloquée {lockout} s")
            raise _locked(lockout)
        raise _fail(401, "bad_pin", "Code PIN incorrect.", attempts_left=security.rate_limiter.attempts_left(ip))
    security.rate_limiter.register_success(ip)
    _grant_session(response, ip)
    _log(db, "devices_login_ok", f"IP {ip}")
    return {"ok": True, "session_minutes": int(security.SESSION_TTL_SECONDS // 60)}


@router.delete("/session")
def close_session(request: Request, response: Response) -> dict[str, bool]:
    security.sessions.revoke(request.cookies.get(security.SESSION_COOKIE) or request.cookies.get(security.STORAGE_SESSION_COOKIE))
    for name, path in SESSION_COOKIES:
        response.delete_cookie(name, path=path)
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


_AUDIO_META_KEY = "devices_audio_meta"
_AUDIO_META_MAX = 200
_ALIAS_MAX = 60


def _load_audio_meta(db: Session) -> dict[str, dict[str, Any]]:
    raw = _get_setting(db, _AUDIO_META_KEY)
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _with_meta(entry: dict[str, Any], meta: dict[str, dict[str, Any]]) -> dict[str, Any]:
    info = meta.get(str(entry.get("id")), {})
    return {**entry, "alias": info.get("alias") or None, "hidden": bool(info.get("hidden"))}


@router.get("/audio")
async def audio_list(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    listing = await _guard(service.driver.audio_list())
    if listing.get("supported"):
        meta = _load_audio_meta(db)
        listing = {**listing, "devices": [_with_meta(d, meta) for d in listing.get("devices", [])]}
    return listing


@router.get("/audio/details")
async def audio_details(id: str, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    details = await _guard(service.driver.audio_details(id))
    return _with_meta(details, _load_audio_meta(db)) if details.get("supported") else details


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


@router.post("/audio/balance")
async def audio_balance(payload: AudioBalanceRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if not (-1.0 <= payload.balance <= 1.0):
        raise _fail(400, "bad_balance", "La balance doit être comprise entre -1 et 1.")
    await _guard(service.driver.audio_set_balance(payload.id, payload.balance))
    return {"ok": True}


@router.post("/audio/test")
async def audio_test(payload: AudioToneRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    if payload.channel not in ("left", "right", "both"):
        raise _fail(400, "bad_channel", "Canal de test inconnu.")
    await _guard(service.driver.audio_test_tone(payload.id, payload.channel))
    return {"ok": True}


@router.post("/audio/profile")
async def audio_profile(payload: AudioProfileRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    await _guard(service.driver.audio_set_profile(payload.id, payload.index))
    return {"ok": True}


@router.put("/audio/meta")
def audio_meta(payload: AudioMetaRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Nom personnalisé et masquage d'une sortie : réglages de Bobine, communs à toutes les plateformes."""
    if not payload.id or len(payload.id) > 256:
        raise _fail(400, "bad_id", "Identifiant de sortie invalide.")
    meta = _load_audio_meta(db)
    entry = dict(meta.get(payload.id, {}))
    if payload.alias is not None:
        alias = payload.alias.strip()
        if len(alias) > _ALIAS_MAX or any(ord(c) < 32 for c in alias):
            raise _fail(400, "bad_alias", f"Le nom doit faire au plus {_ALIAS_MAX} caractères, sans caractère de contrôle.")
        if alias:
            entry["alias"] = alias
        else:
            entry.pop("alias", None)
    if payload.hidden is not None:
        if payload.hidden:
            entry["hidden"] = True
        else:
            entry.pop("hidden", None)
    if entry:
        if payload.id not in meta and len(meta) >= _AUDIO_META_MAX:
            raise _fail(400, "too_many", "Trop de sorties personnalisées.")
        meta[payload.id] = entry
    else:
        meta.pop(payload.id, None)
    _set_setting(db, _AUDIO_META_KEY, json.dumps(meta, ensure_ascii=False) if meta else None)
    return {"ok": True, "alias": entry.get("alias"), "hidden": bool(entry.get("hidden"))}


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


@router.post("/bluetooth/permission")
async def bluetooth_permission(_: Access = Depends(require_access)) -> dict[str, bool]:
    """Android : affiche sur l'appareil la demande d'autorisation « Appareils à proximité »."""
    await _guard(service.driver.bluetooth_request_permission())
    return {"ok": True}


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
# Carte des périphériques
# ---------------------------------------------------------------------------


@router.get("/topology")
async def topology(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Graphe machine → sorties audio, Bluetooth, Wi-Fi, Ethernet, écrans et télécommandes Bobine."""
    import asyncio
    import socket as _socket

    from app.devices.topology import build_topology, ethernet_interfaces
    from app.utils.ws_manager import manager as ws_manager

    async def safe(coro):
        try:
            return await coro
        except DeviceError:
            return None
        except Exception as exc:  # une source en panne n'empêche jamais la carte
            logger.debug("Carte des périphériques : source indisponible (%s)", exc)
            return None

    driver = service.driver
    audio, bluetooth, wifi = await asyncio.gather(safe(driver.audio_list()), safe(driver.bluetooth_status()), safe(driver.wifi_status()))
    if audio and audio.get("supported"):
        meta = _load_audio_meta(db)
        audio = {**audio, "devices": [_with_meta(d, meta) for d in audio.get("devices", [])]}
    wifi_subnet = await safe(driver.wifi_interface_subnet())
    ethernets = ethernet_interfaces((wifi or {}).get("interface") if wifi else None)
    machine = {"name": _socket.gethostname(), "platform": get_deployment_profile()}
    return build_topology(
        machine=machine, audio=audio, bluetooth=bluetooth, wifi=wifi, wifi_subnet=wifi_subnet, ethernets=ethernets,
        clients=ws_manager.client_snapshot(), own_ips=security.own_ip_addresses(),
    )


# ---------------------------------------------------------------------------
# Routage audio par sortie radio (phase 2)
# ---------------------------------------------------------------------------


class RoutingRequest(BaseModel):
    channel: str
    sink_id: str | None = None
    fallback: str | None = None
    clear: bool = False


def _route_public(route: dict[str, Any] | None) -> dict[str, Any] | None:
    if route is None:
        return None
    return {k: route[k] for k in ("sink_id", "key", "label", "kind", "fallback")}


async def _routing_view(db: Session) -> dict[str, Any]:
    """État du routage : pour chaque sortie radio, la route mémorisée, sa résolution actuelle, les lecteurs connectés
    (avec ce qu'ils ont pu appliquer) et ce que le serveur a fait. Les adresses des lecteurs ne sortent pas d'ici."""
    caps = await _guard(service.driver.capabilities())
    audio_cap = caps.get("audio_list", {"supported": False})
    sinks = await service.current_sinks()
    routes = load_routes(db)
    managers = get_all_radio_managers()
    outputs: list[dict[str, Any]] = []
    for channel in RADIO_CHANNELS:
        route = routes.get(channel)
        resolution = resolve_route(route, sinks)
        players = [
            {"local": security.is_local_client(str(p["ip"])), "primary": p["primary"], "status": (p["report"] or {}).get("status")}
            for p in ws_manager.route_players(channel)
        ]
        manager = managers.get(channel)
        outputs.append({
            "channel": channel,
            "route": _route_public(route),
            "state": resolution["state"],
            "sink_id": resolution["sink"]["id"] if resolution["sink"] else None,
            "playing": bool(manager and manager.state.get("playing")),
            "players": players,
            "server": service.server_status(channel),
        })
    return {
        "supported": bool(audio_cap.get("supported")),
        "reason": audio_cap.get("reason") or None,
        "server_mechanism": caps.get("audio_route_stream", {"supported": False}),
        "fallbacks": list(FALLBACKS),
        "outputs": outputs,
    }


@router.get("/routing")
async def get_routing(_: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    return await _routing_view(db)


@router.put("/routing")
async def set_routing(payload: RoutingRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Choisit (ou efface) la sortie audio d'une sortie radio, ou change son repli quand la sortie est absente."""
    if payload.channel not in RADIO_CHANNELS:
        raise _fail(400, "bad_channel", "Sortie radio inconnue.")
    if payload.fallback is not None and payload.fallback not in FALLBACKS:
        raise _fail(400, "bad_fallback", "Repli inconnu.")
    routes = load_routes(db)
    current = routes.get(payload.channel)
    if payload.clear:
        routes.pop(payload.channel, None)
        detail = f"{payload.channel} -> défaut"
    elif payload.sink_id:
        sinks = await service.current_sinks()
        if sinks is None:
            raise _fail(501, "unsupported", "Le choix de la sortie audio n'est pas possible sur cette machine.")
        entry = next((s for s in sinks if s.get("id") == payload.sink_id), None)
        if entry is None:
            raise _fail(404, "not_found", "Cette sortie audio n'est plus disponible.")
        entry = _with_meta(entry, _load_audio_meta(db))
        descriptor = describe_sink(entry)
        descriptor["fallback"] = payload.fallback or (current or {}).get("fallback") or FALLBACKS[0]
        routes[payload.channel] = descriptor
        detail = f"{payload.channel} -> {descriptor['label']}"
    elif payload.fallback is not None:
        if current is None:
            raise _fail(400, "no_route", "Aucune sortie n'est choisie pour cette sortie radio.")
        routes[payload.channel] = {**current, "fallback": payload.fallback}
        detail = f"{payload.channel} repli {payload.fallback}"
    else:
        raise _fail(400, "bad_request", "Indiquez une sortie audio, un repli ou l'effacement de la route.")
    save_routes(db, routes)
    _log(db, "devices_audio_route", detail[:120])
    await service.reconcile_routes()
    service.notify("routing")
    return await _routing_view(db)


# ---------------------------------------------------------------------------
# Table de mixage applicative (phase 3)
# ---------------------------------------------------------------------------


class MixerRequest(BaseModel):
    mix: dict | None = None
    sound: dict | None = None


def _mixer_view() -> dict[str, Any]:
    outputs = []
    for channel, manager in get_all_radio_managers().items():
        outputs.append({
            "channel": channel,
            "mix": manager.state.get("mix"),
            "sound": manager.state.get("sound"),
            "playing": bool(manager.state.get("playing")),
        })
    return {"outputs": outputs}


@router.get("/mixer")
async def get_mixer(_: Access = Depends(require_access)) -> dict[str, Any]:
    return _mixer_view()


@router.put("/mixer/{channel}")
async def set_mixer(channel: str, payload: MixerRequest, _: Access = Depends(require_access), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Modifie le mixage et/ou l'égaliseur de la musique d'une sortie radio. Valeurs bornées sans erreur, champs absents
    conservés, persistées puis diffusées au lecteur (mêmes règles que `PUT /api/radio/sound`)."""
    if channel not in RADIO_CHANNELS:
        raise _fail(404, "not_found", "Sortie radio inconnue.")
    manager = get_radio_manager(channel)
    if payload.sound is not None:
        sound = sanitize_sound(payload.sound, base=manager.state.get("sound"))
        save_sound(db, manager.channel, sound)
        await manager.set_sound(sound)
    if payload.mix is not None:
        mix = sanitize_mix(payload.mix, base=manager.state.get("mix"))
        save_mix(db, manager.channel, mix)
        await manager.set_mix(mix)
    return _mixer_view()


# ---------------------------------------------------------------------------
# Réglages du système (Android : Wi-Fi, Bluetooth, son)
# ---------------------------------------------------------------------------


class SystemSettingsRequest(BaseModel):
    target: str


@router.post("/system-settings")
async def open_system_settings(payload: SystemSettingsRequest, _: Access = Depends(require_access)) -> dict[str, bool]:
    """Ouvre l'écran de réglages correspondant SUR la machine (pour l'écran local ou la télécommande)."""
    if payload.target not in ("wifi", "bluetooth", "sound"):
        raise _fail(400, "bad_target", "Réglage inconnu.")
    await _guard(service.driver.open_system_settings(payload.target))
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

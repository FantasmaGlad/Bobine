"""Pilote Android / Android TV : ponts Kotlin par domaine (Chaquopy)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from .base import CAPABILITY_KEYS, DeviceDriver, DeviceError, unsupported

logger = logging.getLogger(__name__)

_STATUS_BY_CODE = {
    "permission_required": 409,
    "not_ready": 409,
    "no_adapter": 501,
    "bad_address": 400,
    "bad_target": 400,
    "not_authorized": 403,
}

_NO_DEFAULT_SINK = "Android ne permet pas à une application de changer la sortie audio : utilisez les réglages du son."
_NO_AUDIO_TOOLS = "Android ne permet pas à une application de régler la balance, de jouer un son de test ni de changer le profil d'une sortie."
_NO_ROUTE = "Android choisit lui-même la sortie du son : le routage de la radio n'est pas possible depuis Bobine."
_NO_BT_CONNECT = "Android ne permet pas de connecter ou d'oublier un appareil déjà appairé : utilisez les réglages Bluetooth."


BRIDGES = {"audio": "AudioBridge", "bluetooth": "BluetoothBridge", "settings": "SettingsBridge"}


def _default_bridges() -> tuple[dict[str, Any], Any]:
    from com.chaquo.python import Python
    from java import jclass

    bridges = {domain: jclass(f"com.bobine.app.{name}").INSTANCE for domain, name in BRIDGES.items()}
    return bridges, Python.getPlatform().getApplication()


class AndroidDriver(DeviceDriver):
    name = "android"

    def __init__(self, bridge_factory: Callable[[], tuple[dict[str, Any], Any]] = _default_bridges) -> None:
        super().__init__()
        self._factory = bridge_factory
        self._bridges: dict[str, Any] | None = None
        self._context: Any = None

    def _ensure(self) -> tuple[dict[str, Any], Any]:
        if self._bridges is None:
            try:
                self._bridges, self._context = self._factory()
            except Exception as exc:
                raise DeviceError("bridge_unavailable", "Le pont Android des périphériques est indisponible.", 501) from exc
        return self._bridges, self._context

    async def _call(self, domain: str, method: str, *args: Any) -> dict[str, Any]:
        def invoke() -> Any:
            bridges, context = self._ensure()
            return getattr(bridges[domain], method)(context, *args)

        try:
            raw = await asyncio.get_running_loop().run_in_executor(None, invoke)
        except DeviceError:
            raise
        except Exception as exc:
            logger.warning("Pont Android %s.%s en échec : %s", domain, method, exc)
            raise DeviceError("bridge_error", "L'appel au système Android a échoué.", 502) from exc
        try:
            data = json.loads(str(raw))
        except ValueError as exc:
            raise DeviceError("bridge_error", "Réponse illisible du pont Android.", 502) from exc
        if isinstance(data, dict) and data.get("error"):
            code = str(data["error"])
            raise DeviceError(code, str(data.get("message") or "Opération refusée par Android."), _STATUS_BY_CODE.get(code, 502))
        return data

    async def _has_bluetooth(self) -> bool:
        def invoke() -> bool:
            bridges, context = self._ensure()
            return bool(bridges["bluetooth"].hasBluetooth(context))

        try:
            return await asyncio.get_running_loop().run_in_executor(None, invoke)
        except Exception as exc:
            logger.warning("Détection du Bluetooth Android impossible : %s", exc)
            return False

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        caps: dict[str, dict[str, Any]] = {key: {"supported": False, "reason": ""} for key in CAPABILITY_KEYS}
        try:
            self._ensure()
        except DeviceError as exc:
            return {key: {"supported": False, "reason": exc.message} for key in CAPABILITY_KEYS}
        has_bt = await self._has_bluetooth()
        yes = {"supported": True}
        caps["audio_list"] = dict(yes)
        caps["audio_set_volume"] = dict(yes)
        caps["audio_set_default"] = {"supported": False, "reason": _NO_DEFAULT_SINK}
        caps["audio_details"] = dict(yes)
        for key in ("audio_balance", "audio_test_tone", "audio_profile"):
            caps[key] = {"supported": False, "reason": _NO_AUDIO_TOOLS}
        caps["audio_route_stream"] = {"supported": False, "reason": _NO_ROUTE}
        for key in ("bluetooth_status", "bluetooth_power", "bluetooth_scan", "bluetooth_pair"):
            caps[key] = dict(yes) if has_bt else {"supported": False, "reason": "Cet appareil n'a pas de Bluetooth."}
        for key in ("bluetooth_connect", "bluetooth_forget"):
            caps[key] = {"supported": False, "reason": _NO_BT_CONNECT}
        caps["system_settings"] = dict(yes)
        return caps

    async def audio_list(self) -> dict[str, Any]:
        return await self._call("audio", "audioList")

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        await self._call("audio", "audioSetVolume", -1.0 if volume is None else float(volume), -1 if muted is None else (1 if muted else 0))
        self._emit("audio")

    async def audio_details(self, device_id: str) -> dict[str, Any]:
        return await self._call("audio", "audioDetails", str(device_id))

    async def bluetooth_status(self) -> dict[str, Any]:
        if not await self._has_bluetooth():
            return unsupported("Cet appareil n'a pas de Bluetooth.")
        try:
            return await self._call("bluetooth", "bluetoothStatus")
        except DeviceError as exc:
            if exc.code == "permission_required":
                return {"supported": True, "powered": False, "discovering": False, "devices": [], "pending_pairing": None,
                        "pairing": None, "permission_required": True, "permission_message": exc.message}
            if exc.code == "no_adapter":
                return unsupported(exc.message)
            raise

    async def bluetooth_request_permission(self) -> None:
        try:
            await self._call("bluetooth", "bluetoothRequestPermission")
        except DeviceError as exc:
            if exc.code != "permission_required":
                raise

    async def bluetooth_set_power(self, on: bool) -> None:
        if not on:
            raise DeviceError("unsupported", "Android ne permet pas de couper le Bluetooth depuis une application : utilisez les réglages Bluetooth.", 501)
        await self._call("bluetooth", "bluetoothRequestEnable")
        self._emit("bluetooth")

    async def bluetooth_scan(self, on: bool) -> None:
        await self._call("bluetooth", "bluetoothScan", bool(on))
        self._emit("bluetooth")

    async def bluetooth_pair(self, address: str) -> None:
        await self._call("bluetooth", "bluetoothPair", address)
        self._emit("bluetooth")

    async def open_system_settings(self, target: str) -> None:
        await self._call("settings", "openSettings", target)

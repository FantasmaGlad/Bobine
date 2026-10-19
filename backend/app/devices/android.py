"""Pilote Android / Android TV : pont Kotlin `DeviceBridge` (Chaquopy).

Limites d'Android, assumées et déclarées par les capacités : pas de changement de sortie audio par
défaut, pas de connexion/oubli d'un appareil Bluetooth déjà appairé, Wi-Fi en lecture seule et sans
nom de réseau (la lecture du SSID exigerait la localisation précise, permission sensible que Bobine ne
demande pas) ; pour le reste, des liens vers les réglages d'Android (`open_system_settings`).
Les appels Java sont bloquants (profils Bluetooth) : ils s'exécutent hors de la boucle d'évènements.
"""

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
_NO_BT_CONNECT = "Android ne permet pas de connecter ou d'oublier un appareil déjà appairé : utilisez les réglages Bluetooth."
_NO_WIFI = "Depuis Android 10, une application ne peut plus gérer le Wi-Fi : utilisez les réglages du système."


def _default_bridge() -> tuple[Any, Any]:
    from com.chaquo.python import Python  # Chaquopy
    from java import jclass

    return jclass("com.bobine.app.DeviceBridge").INSTANCE, Python.getPlatform().getApplication()


class AndroidDriver(DeviceDriver):
    name = "android"

    def __init__(self, bridge_factory: Callable[[], tuple[Any, Any]] = _default_bridge) -> None:
        super().__init__()
        self._factory = bridge_factory
        self._bridge: Any = None
        self._context: Any = None

    def _ensure(self) -> tuple[Any, Any]:
        if self._bridge is None:
            try:
                self._bridge, self._context = self._factory()
            except Exception as exc:
                raise DeviceError("bridge_unavailable", "Le pont Android des périphériques est indisponible.", 501) from exc
        return self._bridge, self._context

    async def _call(self, method: str, *args: Any) -> dict[str, Any]:
        def invoke() -> Any:
            bridge, context = self._ensure()
            return getattr(bridge, method)(context, *args)

        try:
            raw = await asyncio.get_running_loop().run_in_executor(None, invoke)
        except DeviceError:
            raise
        except Exception as exc:  # exception Java ou Chaquopy : jamais une 500
            logger.warning("DeviceBridge.%s a échoué : %s", method, exc)
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
            bridge, context = self._ensure()
            return bool(bridge.hasBluetooth(context))

        try:
            return await asyncio.get_running_loop().run_in_executor(None, invoke)
        except Exception:
            return False

    # ------------------------------------------------------------------ capacités
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
        for key in ("bluetooth_status", "bluetooth_power", "bluetooth_scan", "bluetooth_pair"):
            caps[key] = dict(yes) if has_bt else {"supported": False, "reason": "Cet appareil n'a pas de Bluetooth."}
        for key in ("bluetooth_connect", "bluetooth_forget"):
            caps[key] = {"supported": False, "reason": _NO_BT_CONNECT}
        caps["wifi_status"] = dict(yes)
        for key in ("wifi_power", "wifi_scan", "wifi_connect", "wifi_forget"):
            caps[key] = {"supported": False, "reason": _NO_WIFI}
        caps["system_settings"] = dict(yes)
        return caps

    # ------------------------------------------------------------------ audio
    async def audio_list(self) -> dict[str, Any]:
        return await self._call("audioList")

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        # Android n'a qu'un volume média global (celui de la sortie active), pas de volume par sortie.
        await self._call("audioSetVolume", -1.0 if volume is None else float(volume), -1 if muted is None else (1 if muted else 0))
        self._emit("audio")

    # ------------------------------------------------------------------ Bluetooth
    async def bluetooth_status(self) -> dict[str, Any]:
        if not await self._has_bluetooth():
            return unsupported("Cet appareil n'a pas de Bluetooth.")
        try:
            return await self._call("bluetoothStatus")
        except DeviceError as exc:
            if exc.code == "permission_required":  # état normal avant autorisation : pas une erreur
                return {"supported": True, "powered": False, "discovering": False, "devices": [], "pending_pairing": None,
                        "pairing": None, "permission_required": True, "permission_message": exc.message}
            if exc.code == "no_adapter":
                return unsupported(exc.message)
            raise

    async def bluetooth_request_permission(self) -> None:
        try:
            await self._call("bluetoothRequestPermission")
        except DeviceError as exc:
            if exc.code != "permission_required":  # la boîte de dialogue vient d'être affichée : c'est attendu
                raise

    async def bluetooth_set_power(self, on: bool) -> None:
        if not on:
            raise DeviceError("unsupported", "Android ne permet pas de couper le Bluetooth depuis une application : utilisez les réglages Bluetooth.", 501)
        await self._call("bluetoothRequestEnable")
        self._emit("bluetooth")

    async def bluetooth_scan(self, on: bool) -> None:
        await self._call("bluetoothScan", bool(on))
        self._emit("bluetooth")

    async def bluetooth_pair(self, address: str) -> None:
        await self._call("bluetoothPair", address)
        self._emit("bluetooth")

    # ------------------------------------------------------------------ Wi-Fi (lecture seule)
    async def wifi_status(self) -> dict[str, Any]:
        return await self._call("wifiStatus")

    async def open_system_settings(self, target: str) -> None:
        await self._call("openSettings", target)

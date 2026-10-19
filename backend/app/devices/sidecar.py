"""Pilote Windows / macOS : sidecar Rust `bobine-devices` (JSON-RPC 2.0 sur stdin/stdout).

Le binaire est lancé À LA DEMANDE, sous le même compte que le backend, et arrêté avec lui ; aucun port
réseau. Une requête = une réponse (sérialisées par un verrou), avec délai d'expiration : un sidecar
bloqué ou planté est tué puis relancé au prochain appel, sans jamais toucher à la diffusion en cours.

Garde-fou du cahier des charges : tant qu'une plateforme n'est pas validée sur du matériel réel, ses
fonctions restent « non prises en charge » ; la variable `BOBINE_DEVICES_EXPERIMENTAL=1` les débloque
pour essai.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from .base import DeviceDriver, DeviceError, no_capabilities, unsupported

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = 1
BINARY_NAME = "bobine-devices"
EXPERIMENTAL_ENV = "BOBINE_DEVICES_EXPERIMENTAL"
BINARY_ENV = "BOBINE_DEVICES_SIDECAR"
REQUEST_TIMEOUT = 50.0
_HELLO_TIMEOUT = 10.0
_CAPS_TTL = 30.0

_PLATFORM_LABEL = {"windows": "Windows", "macos": "macOS"}
_STATUS_BY_CODE = {"unsupported": 501, "tool_missing": 501, "timeout": 504, "wifi_auth_failed": 400, "not_found": 404}


def find_binary(profile: str) -> list[str] | None:
    """Emplacements habituels du sidecar : variable d'environnement, à côté de l'exécutable (paquets
    Windows/macOS), puis dépôt de développement. Renvoie la ligne de commande ou None."""
    suffix = ".exe" if os.name == "nt" else ""
    candidates: list[Path] = []
    override = os.environ.get(BINARY_ENV)
    if override:
        candidates.append(Path(override))
    exe_dir = Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False):
        candidates += [exe_dir / f"{BINARY_NAME}{suffix}", exe_dir.parent / "Resources" / f"{BINARY_NAME}{suffix}"]
    repo_root = Path(__file__).resolve().parents[3]
    candidates.append(repo_root / "devices" / "target" / "release" / f"{BINARY_NAME}{suffix}")
    for path in candidates:
        if path.is_file():
            return [str(path)]
    return None


class SidecarDriver(DeviceDriver):
    name = "sidecar"

    def __init__(self, profile: str, command: list[str] | None = None, experimental: bool | None = None) -> None:
        super().__init__()
        self.profile = profile
        self._command = command if command is not None else find_binary(profile)
        self._experimental = experimental if experimental is not None else os.environ.get(EXPERIMENTAL_ENV) == "1"
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._next_id = 0
        self._hello: dict[str, Any] | None = None
        self._caps_at = 0.0

    # ------------------------------------------------------------------ garde-fous
    def _blocked_reason(self) -> str | None:
        label = _PLATFORM_LABEL.get(self.profile, self.profile)
        if not self._experimental:
            return (
                f"La prise en charge de {label} est en cours de validation sur matériel réel ; "
                f"définissez {EXPERIMENTAL_ENV}=1 pour l'essayer."
            )
        if not self._command:
            return f"Le composant bobine-devices est introuvable sur cette installation ({label})."
        return None

    # ------------------------------------------------------------------ processus
    async def _spawn(self) -> None:
        assert self._command
        self._proc = await asyncio.create_subprocess_exec(
            *self._command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        reply = await self._exchange("hello", {}, _HELLO_TIMEOUT)
        if reply.get("protocol_version") != PROTOCOL_VERSION:
            await self._kill()
            raise DeviceError(
                "sidecar_version",
                f"Version du protocole incompatible (attendue {PROTOCOL_VERSION}, reçue {reply.get('protocol_version')}).",
                502,
            )
        self._hello = reply
        self._caps_at = time.monotonic()

    async def _kill(self) -> None:
        proc, self._proc = self._proc, None
        self._hello = None
        if proc is None:
            return
        try:
            if proc.returncode is None:
                proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:  # processus déjà parti
            pass

    async def stop(self) -> None:
        proc = self._proc
        if proc is not None and proc.stdin is not None:
            try:
                proc.stdin.close()  # fin de l'entrée = arrêt propre du sidecar
                await asyncio.wait_for(proc.wait(), timeout=2)
            except Exception:
                pass
        await self._kill()

    async def _exchange(self, method: str, params: dict[str, Any], timeout: float) -> Any:
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdout is None:
            raise DeviceError("sidecar_down", "Le composant de périphériques n'est pas démarré.", 502)
        self._next_id += 1
        request_id = self._next_id
        line = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n"
        try:
            proc.stdin.write(line.encode())
            await proc.stdin.drain()
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            await self._kill()
            raise DeviceError("timeout", "Le composant de périphériques n'a pas répondu dans le délai imparti.", 504) from exc
        except (BrokenPipeError, ConnectionResetError, OSError) as exc:
            await self._kill()
            raise DeviceError("sidecar_down", "Le composant de périphériques s'est arrêté.", 502) from exc
        if not raw:
            await self._kill()
            raise DeviceError("sidecar_down", "Le composant de périphériques s'est arrêté.", 502)
        try:
            message = json.loads(raw)
        except ValueError as exc:
            await self._kill()
            raise DeviceError("sidecar_protocol", "Réponse illisible du composant de périphériques.", 502) from exc
        if message.get("id") != request_id:
            await self._kill()
            raise DeviceError("sidecar_protocol", "Réponse désynchronisée du composant de périphériques.", 502)
        if "error" in message:
            err = message["error"] or {}
            code = (err.get("data") or {}).get("code") or ("bad_params" if err.get("code") == -32602 else "sidecar_error")
            status = 400 if err.get("code") == -32602 else _STATUS_BY_CODE.get(code, 502)
            raise DeviceError(code, str(err.get("message") or "Erreur du composant de périphériques."), status)
        return message.get("result")

    async def _rpc(self, method: str, params: dict[str, Any] | None = None, timeout: float = REQUEST_TIMEOUT) -> Any:
        reason = self._blocked_reason()
        if reason:
            raise DeviceError("unsupported", reason, 501)
        async with self._lock:
            if self._proc is None or self._proc.returncode is not None:
                await self._kill()
                try:
                    await self._spawn()
                except DeviceError:
                    raise
                except OSError as exc:
                    raise DeviceError("sidecar_down", f"Impossible de lancer le composant de périphériques : {exc.strerror or exc}", 502) from exc
            return await self._exchange(method, params or {}, timeout)

    # ------------------------------------------------------------------ capacités
    async def capabilities(self) -> dict[str, dict[str, Any]]:
        reason = self._blocked_reason()
        if reason:
            return no_capabilities(reason)
        try:
            if self._hello is None or time.monotonic() - self._caps_at > _CAPS_TTL:
                async with self._lock:
                    if self._proc is None or self._proc.returncode is not None:
                        await self._kill()
                        await self._spawn()
                    else:
                        self._hello = await self._exchange("hello", {}, _HELLO_TIMEOUT)
                        self._caps_at = time.monotonic()
            caps = (self._hello or {}).get("capabilities") or {}
        except DeviceError as exc:
            return no_capabilities(exc.message)
        return caps or no_capabilities("Le composant de périphériques ne déclare aucune capacité.")

    # ------------------------------------------------------------------ audio
    async def _list(self, method: str) -> dict[str, Any]:
        reason = self._blocked_reason()
        if reason:
            return unsupported(reason)
        try:
            result = await self._rpc(method)
        except DeviceError as exc:
            if exc.code in ("unsupported", "tool_missing"):
                return unsupported(exc.message)
            raise
        return result if isinstance(result, dict) else unsupported("Réponse inattendue du composant de périphériques.")

    async def audio_list(self) -> dict[str, Any]:
        return await self._list("audio.list")

    async def audio_set_default(self, device_id: str) -> None:
        await self._rpc("audio.set_default", {"id": device_id})
        self._emit("audio")

    async def audio_set_volume(self, device_id: str, volume: float | None, muted: bool | None) -> None:
        await self._rpc("audio.set_volume", {"id": device_id, "volume": volume, "muted": muted})
        self._emit("audio")

    # ------------------------------------------------------------------ Bluetooth
    async def bluetooth_status(self) -> dict[str, Any]:
        return await self._list("bluetooth.status")

    async def bluetooth_set_power(self, on: bool) -> None:
        await self._rpc("bluetooth.set_power", {"on": on})
        self._emit("bluetooth")

    async def bluetooth_scan(self, on: bool) -> None:
        await self._rpc("bluetooth.scan", {"on": on}, timeout=60)
        self._emit("bluetooth")

    async def bluetooth_pair(self, address: str) -> None:
        await self._rpc("bluetooth.pair", {"address": address}, timeout=60)
        self._emit("bluetooth")

    async def bluetooth_connect(self, address: str) -> None:
        await self._rpc("bluetooth.connect", {"address": address})
        self._emit("bluetooth")

    async def bluetooth_disconnect(self, address: str) -> None:
        await self._rpc("bluetooth.disconnect", {"address": address})
        self._emit("bluetooth")

    async def bluetooth_forget(self, address: str) -> None:
        await self._rpc("bluetooth.forget", {"address": address})
        self._emit("bluetooth")

    # ------------------------------------------------------------------ Wi-Fi
    async def wifi_status(self) -> dict[str, Any]:
        return await self._list("wifi.status")

    async def wifi_set_power(self, on: bool) -> None:
        await self._rpc("wifi.set_power", {"on": on})
        self._emit("wifi")

    async def wifi_scan(self) -> None:
        await self._rpc("wifi.scan")
        self._emit("wifi")

    async def wifi_current_connection(self) -> str | None:
        result = await self._rpc("wifi.current_connection")
        return result if isinstance(result, str) and result else None

    async def wifi_connect(self, ssid: str, password: str | None) -> None:
        params: dict[str, Any] = {"ssid": ssid}
        if password:
            params["password"] = password
        await self._rpc("wifi.connect", params, timeout=90)
        self._emit("wifi")

    async def wifi_activate(self, connection: str) -> None:
        await self._rpc("wifi.activate", {"connection": connection}, timeout=90)
        self._emit("wifi")

    async def wifi_forget(self, ssid: str) -> None:
        await self._rpc("wifi.forget", {"ssid": ssid})
        self._emit("wifi")

    async def wifi_interface_subnet(self) -> str | None:
        try:
            result = await self._rpc("wifi.subnet")
        except DeviceError:
            return None
        return result if isinstance(result, str) and result else None

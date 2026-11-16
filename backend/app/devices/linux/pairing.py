"""Appairage Bluetooth : tâche de fond et confirmation relayée à l'interface."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..base import DeviceError

logger = logging.getLogger(__name__)

_PAIR_PROMPT_TIMEOUT = 60.0


class PairingMixin:
    async def bluetooth_pair(self, address: str) -> None:
        path = await self._device_path(address)
        if self._pairing and self._pairing.get("state") == "pairing":
            raise DeviceError("busy", "Un appairage est déjà en cours.", 409)
        self._pairing = {"address": address.upper(), "state": "pairing", "error": None}
        self._emit("bluetooth")
        asyncio.create_task(self._pair_task(address.upper(), path))

    async def _pair_task(self, address: str, path: str) -> None:
        from dbus_fast import Variant

        try:
            await self._call(path, "org.bluez.Device1", "Pair")
            try:
                await self._call(path, "org.freedesktop.DBus.Properties", "Set", "ssv", ["org.bluez.Device1", "Trusted", Variant("b", True)])
                await self._call(path, "org.bluez.Device1", "Connect")
            except DeviceError as exc:
                logger.info("Appairé, connexion non établie (%s) : %s", address, exc.message)
            self._pairing = {"address": address, "state": "paired", "error": None}
        except DeviceError as exc:
            self._pairing = {"address": address, "state": "failed", "error": exc.message}
        except Exception as exc:
            logger.warning("Appairage Bluetooth interrompu : %s", exc)
            self._pairing = {"address": address, "state": "failed", "error": "Appairage interrompu."}
        finally:
            self._clear_pending()
            self._emit("bluetooth")

    async def bluetooth_respond_pairing(self, address: str, accept: bool) -> None:
        pending, future = self._pending, self._pending_future
        if not pending or future is None or future.done() or pending["address"].upper() != address.upper():
            raise DeviceError("no_pending", "Aucune demande d'appairage en attente pour cet appareil.", 409)
        future.set_result(bool(accept))

    def _set_pending(self, pending: dict[str, Any]) -> asyncio.Future[bool]:
        self._pending = pending
        self._pending_future = asyncio.get_running_loop().create_future()
        self._emit("bluetooth")
        return self._pending_future

    def _clear_pending(self) -> None:
        self._pending = None
        self._pending_future = None

    async def _agent_confirm(self, address: str, name: str, kind: str, passkey: str | None) -> bool:
        future = self._set_pending({"address": address, "name": name, "kind": kind, "passkey": passkey})
        try:
            return await asyncio.wait_for(future, timeout=_PAIR_PROMPT_TIMEOUT)
        except asyncio.TimeoutError:
            return False
        finally:
            self._clear_pending()
            self._emit("bluetooth")

    async def _device_label(self, path: str) -> tuple[str, str]:
        try:
            props = (await self._bluez_objects()).get(path, {}).get("org.bluez.Device1", {})
            address = str(props.get("Address") or path.rsplit("dev_", 1)[-1].replace("_", ":"))
            return address, str(props.get("Alias") or props.get("Name") or address)
        except DeviceError:
            address = path.rsplit("dev_", 1)[-1].replace("_", ":")
            return address, address

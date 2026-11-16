"""BlueZ par D-Bus : bus, adaptateur, état, recherche, connexion."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..base import DeviceError, unsupported
from .parse.bluetooth import bluez_device_path, is_valid_mac, parse_bluez_objects

logger = logging.getLogger(__name__)

_BLUEZ = "org.bluez"
_AGENT_PATH = "/org/bobine/agent"


class BluetoothMixin:
    async def _probe_bluetooth(self) -> str | None:
        try:
            from dbus_fast import BusType  # noqa: F401
        except ImportError:
            return "Le module dbus-fast n'est pas installé."
        try:
            await self._ensure_bus()
            await self._bluez_objects()
        except DeviceError as exc:
            return exc.message
        status = await self._bluetooth_snapshot()
        if status["adapter_path"] is None:
            return "Aucun adaptateur Bluetooth détecté."
        return None

    async def _ensure_bus(self) -> Any:
        if self._bus is not None:
            return self._bus
        async with self._bus_lock:
            if self._bus is not None:
                return self._bus
            try:
                from dbus_fast import BusType
                from dbus_fast.aio import MessageBus
            except ImportError as exc:
                raise DeviceError("dbus_missing", "Le module dbus-fast n'est pas installé.", 501) from exc
            try:
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            except Exception as exc:
                raise DeviceError("dbus_unavailable", "Le bus système D-Bus est inaccessible pour ce compte.", 502) from exc
            self._bus = bus
            await self._subscribe_bluez_signals(bus)
            await self._register_agent(bus)
            return bus

    async def _call(self, path: str, interface: str, member: str, signature: str = "", body: list[Any] | None = None, destination: str = _BLUEZ) -> list[Any]:
        from dbus_fast import Message, MessageType

        bus = await self._ensure_bus()
        try:
            reply = await asyncio.wait_for(
                bus.call(Message(destination=destination, path=path, interface=interface, member=member, signature=signature, body=body or [])),
                timeout=45,
            )
        except asyncio.TimeoutError as exc:
            raise DeviceError("timeout", "Le Bluetooth n'a pas répondu dans le délai imparti.", 504) from exc
        except Exception as exc:
            self._bus = None
            raise DeviceError("dbus_unavailable", "Le service Bluetooth est inaccessible.", 502) from exc
        if reply.message_type == MessageType.ERROR:
            raise DeviceError(*_bluez_error(reply.error_name, reply.body))
        return list(reply.body)

    async def _bluez_objects(self) -> dict[str, dict[str, dict[str, Any]]]:
        body = await self._call("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
        return {
            path: {iface: {name: variant.value for name, variant in props.items()} for iface, props in ifaces.items()}
            for path, ifaces in body[0].items()
        }

    async def _bluetooth_snapshot(self) -> dict[str, Any]:
        return parse_bluez_objects(await self._bluez_objects())

    async def _subscribe_bluez_signals(self, bus: Any) -> None:
        from dbus_fast import Message, MessageType

        def on_message(msg: Any) -> None:
            if msg.message_type == MessageType.SIGNAL and (msg.path or "").startswith("/org/bluez") and msg.member in (
                "PropertiesChanged", "InterfacesAdded", "InterfacesRemoved"
            ):
                self._emit("bluetooth")

        bus.add_message_handler(on_message)
        try:
            await bus.call(
                Message(
                    destination="org.freedesktop.DBus", path="/org/freedesktop/DBus", interface="org.freedesktop.DBus",
                    member="AddMatch", signature="s", body=["type='signal',sender='org.bluez'"],
                )
            )
        except Exception as exc:
            logger.debug("Abonnement aux signaux BlueZ impossible : %s", exc)

    async def _register_agent(self, bus: Any) -> None:
        try:
            from .agent import make_agent

            self._agent = make_agent(self)
            bus.export(_AGENT_PATH, self._agent)
            await self._call("/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", "os", [_AGENT_PATH, "KeyboardDisplay"])
            await self._call("/org/bluez", "org.bluez.AgentManager1", "RequestDefaultAgent", "o", [_AGENT_PATH])
        except DeviceError as exc:
            logger.info("Agent d'appairage Bluetooth non enregistré : %s", exc.message)
            self._agent = None

    async def bluetooth_status(self) -> dict[str, Any]:
        reason = await self._probe_bluetooth()
        if reason:
            return unsupported(reason)
        snap = await self._bluetooth_snapshot()
        return {
            "supported": True,
            "powered": snap["powered"],
            "discovering": snap["discovering"],
            "adapter_name": snap["adapter_name"],
            "devices": [{k: v for k, v in d.items() if k != "path"} for d in snap["devices"]],
            "pending_pairing": self._pending,
            "pairing": self._pairing,
        }

    async def _adapter_path(self) -> str:
        snap = await self._bluetooth_snapshot()
        if not snap["adapter_path"]:
            raise DeviceError("no_adapter", "Aucun adaptateur Bluetooth détecté.", 501)
        return snap["adapter_path"]

    async def _set_adapter_prop(self, name: str, signature: str, value: Any) -> None:
        from dbus_fast import Variant

        path = await self._adapter_path()
        await self._call(path, "org.freedesktop.DBus.Properties", "Set", "ssv", ["org.bluez.Adapter1", name, Variant(signature, value)])

    async def bluetooth_set_power(self, on: bool) -> None:
        await self._set_adapter_prop("Powered", "b", on)
        self._emit("bluetooth")

    async def bluetooth_scan(self, on: bool) -> None:
        path = await self._adapter_path()
        snap = await self._bluetooth_snapshot()
        if on and not snap["powered"]:
            await self._set_adapter_prop("Powered", "b", True)
        if on == snap["discovering"]:
            return
        await self._call(path, "org.bluez.Adapter1", "StartDiscovery" if on else "StopDiscovery")
        self._emit("bluetooth")

    async def _device_path(self, address: str) -> str:
        if not is_valid_mac(address):
            raise DeviceError("bad_address", "Adresse Bluetooth invalide.", 400)
        return bluez_device_path(await self._adapter_path(), address)

    async def bluetooth_connect(self, address: str) -> None:
        await self._call(await self._device_path(address), "org.bluez.Device1", "Connect")
        self._emit("bluetooth")

    async def bluetooth_disconnect(self, address: str) -> None:
        await self._call(await self._device_path(address), "org.bluez.Device1", "Disconnect")
        self._emit("bluetooth")

    async def bluetooth_forget(self, address: str) -> None:
        adapter = await self._adapter_path()
        await self._call(adapter, "org.bluez.Adapter1", "RemoveDevice", "o", [bluez_device_path(adapter, address) if is_valid_mac(address) else ""])
        self._emit("bluetooth")


def _bluez_error(error_name: str | None, body: list[Any]) -> tuple[str, str, int]:
    text = str(body[0]) if body else ""
    name = (error_name or "").rsplit(".", 1)[-1]
    table = {
        "AlreadyExists": ("already", "Cet appareil est déjà appairé.", 409),
        "AuthenticationFailed": ("pair_failed", "Échec de l'authentification (code refusé).", 400),
        "AuthenticationRejected": ("pair_rejected", "Appairage refusé.", 400),
        "AuthenticationCanceled": ("pair_cancelled", "Appairage annulé.", 400),
        "AuthenticationTimeout": ("timeout", "L'appareil n'a pas répondu à temps.", 504),
        "ConnectionAttemptFailed": ("connect_failed", "Connexion impossible : l'appareil est-il allumé et à portée ?", 502),
        "InProgress": ("busy", "Opération déjà en cours.", 409),
        "NotReady": ("not_ready", "Le Bluetooth n'est pas prêt (est-il activé ?).", 409),
        "NotAvailable": ("not_available", "Opération indisponible pour cet appareil.", 409),
        "DoesNotExist": ("not_found", "Appareil Bluetooth introuvable.", 404),
        "Failed": ("bt_failed", text[:200] or "Opération Bluetooth échouée.", 502),
        "NotAuthorized": ("not_authorized", "Le compte qui exécute Bobine n'a pas le droit d'utiliser le Bluetooth.", 403),
    }
    if "rfkill" in text.lower():
        return ("bluetooth_blocked", "Le Bluetooth est bloqué (interrupteur matériel ou rfkill).", 409)
    return table.get(name, ("bt_failed", text[:200] or "Opération Bluetooth échouée.", 502))

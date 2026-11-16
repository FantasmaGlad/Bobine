"""Pilote Linux : lsblk (inventaire), udisksctl et udisks2 (montage sans privilèges), smartctl, GVFS."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from typing import Any
from app.devices.linux.command import Runner, run_command
from app.storage import portable
from ..base import CAPABILITY_KEYS, DeviceError, StorageDriver
from .errors import _stderr
from .inventory import InventoryMixin
from .maintenance import MaintenanceMixin
from .portable import PortableMixin
from .udisks import UdisksMixin, _UDISKS

logger = logging.getLogger(__name__)






_PROBE_TTL = 30.0


class LinuxStorageDriver(InventoryMixin, MaintenanceMixin, UdisksMixin, PortableMixin, StorageDriver):
    name = "linux"

    def __init__(self, runner: Runner = run_command, *, sys_block: str = "/sys/block", mountinfo_path: str = "/proc/self/mountinfo") -> None:
        super().__init__()
        self._run = runner
        self._sys_block = sys_block
        self._mountinfo_path = mountinfo_path
        self._bus: Any = None
        self._watch_task: asyncio.Task[None] | None = None
        self.push_active = False
        self._probe_cache: tuple[float, dict[str, dict[str, Any]]] | None = None
        self._facts_cache: tuple[float, dict[str, Any]] | None = None
        self._unix_uid = os.getuid() if hasattr(os, "getuid") else 0

    async def start(self) -> None:
        if self._watch_task is None or self._watch_task.done():
            self._watch_task = asyncio.create_task(self._watch_udisks())

    async def stop(self) -> None:
        task, self._watch_task = self._watch_task, None
        if task is not None and not task.done():
            task.cancel()
        bus, self._bus = self._bus, None
        if bus is not None:
            try:
                bus.disconnect()
            except Exception as exc:
                logger.debug("stop : %s", exc)
        self.push_active = False

    async def _watch_udisks(self) -> None:
        try:
            from dbus_fast import BusType, Message, MessageType
            from dbus_fast.aio import MessageBus
        except ImportError:
            return
        while True:
            try:
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
                self._bus = bus

                def handler(message: Any) -> None:
                    if message.message_type == MessageType.SIGNAL and (message.path or "").startswith("/org/freedesktop/UDisks2"):
                        if message.member in ("InterfacesAdded", "InterfacesRemoved", "PropertiesChanged"):
                            self._emit("volumes")

                bus.add_message_handler(handler)
                for member, iface, path_kw in (
                    ("InterfacesAdded", "org.freedesktop.DBus.ObjectManager", "path"),
                    ("InterfacesRemoved", "org.freedesktop.DBus.ObjectManager", "path"),
                    ("PropertiesChanged", "org.freedesktop.DBus.Properties", "path_namespace"),
                ):
                    rule = f"type='signal',sender='{_UDISKS}',interface='{iface}',member='{member}'," + (
                        "path='/org/freedesktop/UDisks2'" if path_kw == "path" else "path_namespace='/org/freedesktop/UDisks2'"
                    )
                    await bus.call(
                        Message(
                            destination="org.freedesktop.DBus", path="/org/freedesktop/DBus", interface="org.freedesktop.DBus",
                            member="AddMatch", signature="s", body=[rule],
                        )
                    )
                self.push_active = True
                await bus.wait_for_disconnect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Surveillance udisks2 indisponible : %s", exc)
            self.push_active = False
            await asyncio.sleep(30)

    async def capabilities(self) -> dict[str, dict[str, Any]]:
        now = time.monotonic()
        if self._probe_cache and now - self._probe_cache[0] < _PROBE_TTL:
            return self._probe_cache[1]
        caps: dict[str, dict[str, Any]] = {k: {"supported": False, "reason": ""} for k in CAPABILITY_KEYS}
        have_lsblk = shutil.which("lsblk") is not None
        caps["inventory"] = {"supported": have_lsblk} if have_lsblk else {"supported": False, "reason": "L'outil lsblk (util-linux) n'est pas installé."}

        udisks_reason = await self._probe_udisks()
        for key in ("mount", "eject"):
            caps[key] = {"supported": udisks_reason is None}
            if udisks_reason:
                caps[key]["reason"] = udisks_reason
        caps["push_events"] = {"supported": self.push_active}
        if not self.push_active:
            caps["push_events"]["reason"] = "Interrogation périodique légère (udisks2 ne signale pas les changements)."

        caps["smart"] = {"supported": True} if shutil.which("smartctl") else {"supported": False, "reason": "L'outil smartctl (paquet smartmontools) n'est pas installé."}
        facts = await self.facts()
        if facts["is_root"] and shutil.which("fstrim"):
            caps["trim"] = {"supported": True}
        else:
            caps["trim"] = {"supported": False, "reason": "TRIM exige les droits d'administrateur : le minuteur fstrim du système s'en charge" if shutil.which("fstrim") else "L'outil fstrim n'est pas installé."}
        caps["standby"] = {"supported": facts["standby_supported"]}
        if not facts["standby_supported"]:
            caps["standby"]["reason"] = "Aucun moyen de mettre un disque en veille sans droits (udisks2 ou hdparm requis)."
        fmt = await self.format_support()
        caps["format"] = {"supported": fmt["supported"]}
        if not fmt["supported"]:
            caps["format"]["reason"] = fmt["reason"]
        portable_ok = shutil.which("gio") is not None
        caps["portable"] = {"supported": portable_ok}
        if not portable_ok:
            caps["portable"]["reason"] = "GVFS n'est pas installé : " + portable.INSTALL_HELP["mtp"]
        self._probe_cache = (now, caps)
        return caps

    async def _probe_udisks(self) -> str | None:
        if shutil.which("udisksctl") is None:
            return "udisks2 n'est pas installé (paquet udisks2) : les supports sont listés mais ne peuvent pas être montés ici."
        try:
            code, _, err = await self._run("udisksctl", "status", timeout=5.0)
        except DeviceError as exc:
            return exc.message
        if code != 0:
            return "Le service udisks2 ne répond pas : " + _stderr(err)
        return None

    async def facts(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._facts_cache and now - self._facts_cache[0] < _PROBE_TTL:
            return self._facts_cache[1]
        is_root = hasattr(os, "geteuid") and os.geteuid() == 0
        timer: bool | None = None
        if shutil.which("systemctl"):
            try:
                code, out, _ = await self._run("systemctl", "is-enabled", "fstrim.timer", timeout=4.0)
                timer = out.strip() == "enabled" if code in (0, 1) else None
            except DeviceError:
                timer = None
        standby = is_root and shutil.which("hdparm") is not None or (shutil.which("busctl") is not None and shutil.which("udisksctl") is not None)
        facts = {"is_root": is_root, "fstrim_timer_enabled": timer, "standby_supported": bool(standby)}
        self._facts_cache = (now, facts)
        return facts


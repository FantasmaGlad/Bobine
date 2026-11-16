"""Appels udisks2 par D-Bus : disques, formats pris en charge, partitionnement et formatage."""

from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
import os
import shutil
from typing import Any
from app.storage.formatting.disks import DISK_COLUMNS, DISK_COLUMNS_FALLBACK, parse_disks
from app.storage.formatting.model import DiskInfo, FormatSpec
from app.storage.formatting.options import SPECS
from ..base import DeviceError
from .errors import classify_dbus_error

logger = logging.getLogger(__name__)


_UDISKS = "org.freedesktop.UDisks2"


_UDISKS_ROOT = "/org/freedesktop/UDisks2"


FORMAT_TIMEOUT = 300.0


class UdisksMixin:
    async def _udisks_call(self, path: str, interface: str, member: str, signature: str, body: list[Any], *, timeout: float = FORMAT_TIMEOUT) -> Any:
        try:
            from dbus_fast import BusType, Message, MessageType
            from dbus_fast.aio import MessageBus
        except ImportError as exc:
            raise DeviceError("format_tool_missing", "Le composant D-Bus (dbus-fast) est absent.", 501) from exc
        bus = None
        try:
            bus = await asyncio.wait_for(MessageBus(bus_type=BusType.SYSTEM).connect(), timeout=10.0)
            reply = await asyncio.wait_for(
                bus.call(Message(destination=_UDISKS, path=path, interface=interface, member=member, signature=signature, body=body)),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise DeviceError("format_failed", "Le système n'a pas répondu à temps.", 504) from exc
        except Exception as exc:  # noqa: BLE001 - tout échec de bus devient une erreur structurée
            if isinstance(exc, DeviceError):
                raise
            raise DeviceError("format_failed", "Le service udisks2 est injoignable.", 502) from exc
        finally:
            if bus is not None:
                try:
                    bus.disconnect()
                except Exception as exc:  # noqa: BLE001
                    logger.debug("_udisks_call : %s", exc)
        if reply.message_type == MessageType.ERROR:
            raise classify_dbus_error(reply.error_name or "", str(reply.body[0]) if reply.body else "")
        return reply.body

    async def disks(self) -> list[DiskInfo]:
        out = await self._lsblk(DISK_COLUMNS, DISK_COLUMNS_FALLBACK, "les disques")
        try:
            disks = parse_disks(out, is_sd_card=self._is_sd)
            result = []
            for disk in disks:
                try:
                    with open(f"/sys/class/block/{disk.name}/diskseq", encoding="ascii") as handle:
                        sequence = handle.read().strip()
                except OSError:
                    sequence = None
                result.append(replace(disk, diskseq=sequence))
            return result
        except (ValueError, KeyError, TypeError) as exc:
            raise DeviceError("inventory_failed", f"Réponse lsblk illisible : {exc}", 502) from exc

    async def format_support(self) -> dict[str, Any]:
        tools = {fs: any(shutil.which(t) for t in spec.tools) for fs, spec in SPECS.items()}
        reason = await self._probe_udisks()
        if reason is None:
            try:
                import dbus_fast  # noqa: F401
            except ImportError:
                reason = "Le composant D-Bus (dbus-fast) est absent."
        if reason is None and not shutil.which("lsblk"):
            reason = "L'outil lsblk (util-linux) n'est pas installé."
        return {"supported": reason is None and any(tools.values()), "reason": reason, "tools": tools}

    @staticmethod
    def _block_path(disk_path: str) -> str:
        return f"{_UDISKS_ROOT}/block_devices/{os.path.basename(disk_path)}"

    async def create_partition_table(self, disk: DiskInfo) -> None:
        await self._udisks_call(self._block_path(disk.path), "org.freedesktop.UDisks2.Block", "Format", "sa{sv}", ["gpt", {}])

    async def create_partition_and_format(self, disk: DiskInfo, spec: FormatSpec) -> str:
        from dbus_fast import Variant

        options: dict[str, Any] = {"auth.no_user_interaction": Variant("b", True), "label": Variant("s", spec.label), "mkfs-args": Variant("as", list(spec.mkfs_args))}
        if spec.take_ownership:
            options["take-ownership"] = Variant("b", True)
        body = await self._udisks_call(
            self._block_path(disk.path), "org.freedesktop.UDisks2.PartitionTable", "CreatePartitionAndFormat", "ttssa{sv}sa{sv}",
            [spec.offset_bytes, 0, spec.partition_guid, spec.partition_name, {}, spec.udisks_type, options],
        )
        created = str(body[0]) if body else ""
        name = created.rsplit("/", 1)[-1]
        if not name:
            raise DeviceError("format_failed", "La partition créée n'a pas pu être identifiée.", 502)
        return f"/dev/{name}"

    async def wipe_disk(self, disk: DiskInfo) -> None:
        await self._udisks_call(self._block_path(disk.path), "org.freedesktop.UDisks2.Block", "Format", "sa{sv}", ["empty", {}])


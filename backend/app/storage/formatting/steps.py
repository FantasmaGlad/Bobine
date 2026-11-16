"""Étapes destructives du formatage : démontage, revérification, table, système de fichiers, attente du disque."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable, TypeVar
from app.devices.base import DeviceError
from app.storage.types import Volume
from .model import DiskInfo, FormatSpec, fingerprint, hardware_identity
from .refusals import FormatRefusal
from .rules import evaluate
from .job import FormatJob


UNMOUNT_TRIES = 4


UNMOUNT_PAUSE = 1.5


SETTLE_SECONDS = 25.0


T = TypeVar("T")


class StepsMixin:
    async def _unmount_all(self, job: FormatJob, disk: DiskInfo) -> DiskInfo:
        self._step(job, "unmount", "running")
        await asyncio.to_thread(os.sync)
        for attempt in range(UNMOUNT_TRIES):
            self._check_cancel(job)
            current = await self._fresh(disk)
            mounted = [p for p in current.partitions if p.mounted]
            if not mounted:
                self._step(job, "unmount", "ok")
                return current
            for part in mounted:
                try:
                    await self.svc.driver.unmount_device(part.path)
                except DeviceError as exc:
                    if exc.code != "busy" or attempt + 1 == UNMOUNT_TRIES:
                        if exc.code == "busy":
                            raise FormatRefusal("format_busy_mounted") from exc
                        raise
            await asyncio.sleep(UNMOUNT_PAUSE if attempt else 0.4)
        raise FormatRefusal("format_busy_mounted")

    async def _fresh(self, disk: DiskInfo) -> DiskInfo:
        for candidate in await self.svc.driver.disks():
            if hardware_identity(candidate) == hardware_identity(disk):
                return candidate
        raise FormatRefusal("format_identity_changed")

    async def _recheck(self, job: FormatJob, planned: DiskInfo, support: dict[str, Any]) -> DiskInfo:
        self._step(job, "recheck", "running")
        self._check_cancel(job)
        disks = await self.svc.driver.disks()
        current = next((d for d in disks if d.path == planned.path), None)
        ctx = await self._context(current, support, ignore_job=job)
        refusal = self._refusal(evaluate(ctx), current)
        if refusal is not None:
            raise refusal
        assert current is not None
        if fingerprint(current) != fingerprint(planned):
            raise FormatRefusal("format_identity_changed")
        if current.mountpoints:
            for part in current.partitions:
                if part.mounted:
                    await self.svc.driver.unmount_device(part.path)
            current = await self._fresh(current)
            if current.mountpoints:
                raise FormatRefusal("format_busy_mounted")
        self._check_cancel(job)
        self._step(job, "recheck", "ok")
        return current

    async def _erase_and_format(self, job: FormatJob, disk: DiskInfo, spec: FormatSpec) -> None:
        job.point_of_no_return = True
        self._step(job, "table", "running")
        await self.svc.driver.create_partition_table(disk)
        await asyncio.sleep(0.8)
        self._step(job, "table", "ok")
        self._step(job, "format", "running")
        job.error = None
        await self.svc.driver.create_partition_and_format(await self._fresh(disk), spec)
        self._step(job, "format", "ok")

    async def _wait_new_disk(self, disk: DiskInfo, spec: FormatSpec) -> DiskInfo | None:
        async def formatted() -> DiskInfo | None:
            for candidate in await self.svc.driver.disks():
                if candidate.path == disk.path:
                    if hardware_identity(candidate) != hardware_identity(disk):
                        raise FormatRefusal("format_identity_changed")
                    parts = [p for p in candidate.partitions if p.fstype]
                    if parts and parts[0].uuid:
                        return candidate
            return None

        return await _poll(formatted, 0.5)

    async def _wait_volume(self, device: str) -> Volume | None:
        async def mounted() -> Volume | None:
            await self.svc.refresh()
            return next((v for v in self.svc._by_key.values() if v.device == device), None)

        return await _poll(mounted, 0.6)


async def _poll(probe: Callable[[], Awaitable[T | None]], interval: float) -> T | None:
    deadline = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < deadline:
        found = await probe()
        if found is not None:
            return found
        await asyncio.sleep(interval)
    return None

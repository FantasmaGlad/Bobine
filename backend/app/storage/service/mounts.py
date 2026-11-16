"""Montage, démontage, éjection et supports portables (téléphones)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from app.devices.base import DeviceError
from app.storage import fsadvisor, library, longevity
from app.storage.lsblk import media_for_kind
from app.storage.types import Volume

from .constants import MOUNT_SETTLE_TRIES, UNMOUNT_BUSY_TRIES, UNMOUNT_BUSY_SECONDS, MOUNT_SETTLE_SECONDS
from .source import Source


class MountMixin:
    def _settings_for(self, vol: Volume) -> dict[str, Any]:
        from app.database import SessionLocal

        with SessionLocal() as db:
            return library.settings_of(db, library.get_by_uuid(db, vol.fs_uuid))

    async def _effective_settings(self, vol: Volume) -> dict[str, Any]:
        return await asyncio.to_thread(self._settings_for, vol)

    def request_refresh(self) -> None:
        """Demande une relecture immédiate de l'inventaire (retrait brutal soupçonné par un flux)."""
        self._on_driver_event("volumes")

    def touch(self, key: str | None) -> None:
        if key:
            self._activity[key] = time.monotonic()

    def touch_storage(self, storage_id: int | None) -> None:
        """Appelé à chaque lecture d'un média externe : réveille le suivi d'inactivité (veille des disques)."""
        if storage_id is None:
            return
        root = self._online.get(storage_id)
        if not root:
            return
        for vol in self._by_key.values():
            if vol.mountpoint == root:
                self._activity[vol.key] = time.monotonic()
                return

    async def _mount_volume(self, vol: Volume, *, writable: bool, settings: dict[str, Any]) -> str:
        options = longevity.mount_options(settings, writable=writable)
        mountpoint: str | None = None
        for attempt in range(MOUNT_SETTLE_TRIES):
            try:
                mountpoint = await self.driver.mount(vol, options)
                break
            except DeviceError as exc:
                if exc.code == "option_not_permitted":
                    mountpoint = await self.driver.mount(vol, ["rw" if writable else "ro"])
                    break
                if exc.code == "unsupported_fs" and attempt + 1 < MOUNT_SETTLE_TRIES:
                    await asyncio.sleep(MOUNT_SETTLE_SECONDS)
                    continue
                if exc.code == "dirty":
                    self._dirty.add(vol.key)
                raise
        assert mountpoint is not None
        self._dirty.discard(vol.key)
        self._log("storage_mounted", f"{vol.display_name} ({'rw' if writable else 'ro'})")
        await self._refresh_soon()
        return mountpoint

    async def _refresh_soon(self) -> None:
        if self._wake is not None:
            self._wake.set()

    async def _sync_now(self) -> None:
        await asyncio.to_thread(os.sync)

    async def _unmount_volume(self, vol: Volume) -> None:
        if self._busy.get(vol.key):
            raise DeviceError("busy", "Un import ou un export utilise ce support : annulez-le ou attendez sa fin.", 409)
        await self._sync_now()
        for attempt in range(UNMOUNT_BUSY_TRIES):
            try:
                await self.driver.unmount(vol)
                return
            except DeviceError as exc:
                if exc.code != "busy" or attempt + 1 == UNMOUNT_BUSY_TRIES:
                    raise
                await asyncio.sleep(UNMOUNT_BUSY_SECONDS)

    async def _remount(self, vol: Volume, *, writable: bool, settings: dict[str, Any]) -> str:
        await self._unmount_volume(vol)
        return await self._mount_volume(vol, writable=writable, settings=settings)

    async def mount(self, key: str, mode: str = "ro", *, _format_job: str | None = None) -> dict[str, Any]:
        if mode not in ("ro", "rw"):
            raise DeviceError("bad_mode", "Mode de montage inconnu.", 400)
        async with self._lock:
            vol = self._need(key, format_job=_format_job)
            settings = await self._effective_settings(vol)
            writable = mode == "rw"
            if writable:
                assessment = fsadvisor.assess_filesystem(vol.fstype, media=media_for_kind(vol.kind), dirty=vol.key in self._dirty)
                if not assessment.write_allowed:
                    raise DeviceError("write_refused", "Ce système de fichiers n'est pas fiable en écriture (voir le verdict) : lecture seule uniquement.", 409)
            if vol.mounted and vol.mounted_read_only == (not writable):
                return {"mounted": True, "mode": mode, "changed": False}
            if vol.mounted:
                await self._remount(vol, writable=writable, settings=settings)
            else:
                await self._mount_volume(vol, writable=writable, settings=settings)
            self.touch(key)
        await self.refresh()
        return {"mounted": True, "mode": mode, "changed": True}

    async def unmount(self, key: str) -> dict[str, Any]:
        async with self._lock:
            vol = self._need(key)
            if vol.mounted:
                await self._unmount_volume(vol)
                self._log("storage_unmounted", vol.display_name)
        await self.refresh()
        return {"mounted": False}

    async def eject(self, key: str) -> dict[str, Any]:
        """Retrait sûr : synchronisation, démontage, extinction du support."""
        async with self._lock:
            vol = self._need(key)
            if self._busy.get(key):
                raise DeviceError("busy", "Un import ou un export utilise ce support : annulez-le ou attendez sa fin.", 409)
            self._ejecting.add(key)
            try:
                if vol.mounted:
                    await self._unmount_volume(vol)
                powered_off = await self.driver.power_off(vol)
            except DeviceError:
                self._ejecting.discard(key)
                raise
            self._log("storage_ejected", vol.display_name)
        await self.refresh()
        return {"ejected": True, "powered_off": powered_off}

    def _source(self, key: str) -> Source:
        if key.startswith("p-"):
            root = self._portable_roots.get(key)
            if not root or not os.path.isdir(root):
                raise DeviceError("not_mounted", "L'appareil n'est pas ouvert : ouvrez-le d'abord.", 409)
            return Source(key, root, True, None, key)
        vol = self._need(key)
        if not vol.mounted or not vol.mountpoint:
            raise DeviceError("not_mounted", "Le support n'est pas monté : ouvrez-le d'abord.", 409)
        return Source(key, vol.mountpoint, False, vol, vol.fs_uuid or key)

    async def portable(self) -> dict[str, Any]:
        status = await self.driver.portable_status()
        for dev in status.get("devices", []):
            if dev.get("state") == "mounted" and dev["id"] not in self._portable_roots:
                dev["state"] = "ready"
        return status

    async def portable_mount(self, device_id: str) -> dict[str, Any]:
        result = await self.driver.portable_mount(device_id)
        self._portable_roots[device_id] = result["root"]
        self.notify("portable")
        return {"id": device_id, "mounted": True}

    async def portable_unmount(self, device_id: str) -> dict[str, Any]:
        self._portable_roots.pop(device_id, None)
        await self.driver.portable_unmount(device_id)
        self.notify("portable")
        return {"mounted": False}

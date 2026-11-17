"""Surveillance : démarrage, boucle de détection, ingestion de l'inventaire, synchronisation des bibliothèques."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from app.devices.base import DeviceError
from app.storage import availability, library, verified_copy
from app.storage.lsblk import duplicate_uuids
from app.storage.types import Inventory, Volume

from .constants import POLL_SECONDS, POLL_SAFETY_SECONDS, SETTLE_SECONDS, MOUNT_RETRY, RECENT_KEEP

logger = logging.getLogger(__name__)


class MonitorMixin:
    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        from app.database import SessionLocal

        def _offline() -> None:
            with SessionLocal() as db:
                library.mark_all_offline(db)

        try:
            await asyncio.to_thread(_offline)
            availability.set_online({})
            await asyncio.to_thread(verified_copy.purge_staging)
        except Exception as exc:
            logger.warning("Initialisation du stockage externe : %s", exc)
        try:
            await self.driver.start()
        except Exception as exc:
            logger.warning("Démarrage du pilote de stockage impossible : %s", exc)
        try:
            await asyncio.wait_for(self.refresh(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning("Premier instantané du stockage externe : délai dépassé, la surveillance continue en arrière-plan.")
        except Exception as exc:
            logger.warning("Premier instantané du stockage externe impossible : %s", exc)
        if self._monitor is None or self._monitor.done():
            self._monitor = asyncio.create_task(self._monitor_loop())

    async def stop(self) -> None:
        monitor, self._monitor = self._monitor, None
        if monitor is not None and not monitor.done():
            monitor.cancel()
        if self._driver is not None:
            try:
                await self._driver.stop()
            except Exception as exc:
                logger.debug("Arrêt du pilote de stockage : %s", exc)

    async def _monitor_loop(self) -> None:
        while True:
            push = bool(getattr(self.driver, "push_active", False))
            try:
                assert self._wake is not None
                await asyncio.wait_for(self._wake.wait(), timeout=POLL_SAFETY_SECONDS if push else POLL_SECONDS)
                await asyncio.sleep(SETTLE_SECONDS)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                raise
            if self._wake is not None:
                self._wake.clear()
            try:
                await self.refresh()
                await self._maintenance()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Surveillance du stockage externe : %s", exc, exc_info=True)

    @staticmethod
    def protected_paths() -> list[str]:
        from app.config import DATA_ROOT, settings

        candidates = [
            settings.media_dir, settings.watch_dir, settings.thumbnails_dir, settings.backgrounds_dir,
            settings.backgrounds_watch_dir, settings.audio_dir, settings.audio_watch_dir, settings.radio_dir,
            settings.radio_covers_dir, settings.radio_announcements_dir, settings.radio_watch_dir,
            settings.branding_dir, settings.logs_dir, settings.subtitles_dir, str(DATA_ROOT),
        ]
        if settings.database_url.startswith("sqlite:///"):
            candidates.append(os.path.dirname(settings.database_url[len("sqlite:///"):]))
        return sorted({os.path.realpath(p) for p in candidates if p})

    async def refresh(self) -> None:
        async with self._lock:
            try:
                inventory = await self.driver.inventory(self.protected_paths())
                self._last_error = None
            except DeviceError as exc:
                self._last_error = {"code": exc.code, "message": exc.message}
                self._ready = True
                return
            await self._ingest(inventory)
            self._ready = True

    async def _ingest(self, inventory: Inventory) -> None:
        previous = self._by_key
        current = {v.key: v for v in inventory.volumes}
        changes: list[str] = []
        now = time.time()
        for key, vol in current.items():
            old = previous.get(key)
            if old is None:
                changes.append("added")
                self._log("storage_connected", f"{vol.display_name} ({vol.fstype or '?'})")
            elif old.mounted != vol.mounted:
                changes.append("mounted" if vol.mounted else "unmounted")
        for key, old in previous.items():
            if key in current:
                continue
            abrupt = old.mounted and key not in self._ejecting and key not in self._formatting
            changes.append("removed_abruptly" if abrupt else "removed")
            self._log("storage_removed_abruptly" if abrupt else "storage_removed", old.display_name)
            self._recent.append({"key": key, "name": old.display_name, "at": now, "abrupt": abrupt})
            self._ejecting.discard(key)
            self._busy.pop(key, None)
            self._rw_lease.discard(key)
            self._health.pop(key, None)
            self._dirty.discard(key)
        self._recent = [r for r in self._recent if now - r["at"] < RECENT_KEEP][-20:]
        self._inventory = inventory
        self._by_key = current
        await self._sync_libraries()
        if changes:
            self.notify("volumes", changes)

    async def _sync_libraries(self) -> None:
        from app.database import SessionLocal

        def _libs() -> list[dict[str, Any]]:
            with SessionLocal() as db:
                return [
                    {"id": lib.id, "uuid": lib.fs_uuid, "enabled": lib.enabled, "settings": library.settings_of(db, lib)}
                    for lib in library.all_libraries(db)
                ]

        libs = await asyncio.to_thread(_libs)
        if not libs:
            return
        duplicates = duplicate_uuids(self._inventory.volumes)
        by_uuid = {v.fs_uuid.lower(): v for v in self._inventory.volumes if v.fs_uuid and v.fs_uuid.lower() not in duplicates}
        online: dict[int, str] = {}
        for lib in libs:
            vol = by_uuid.get((lib["uuid"] or "").lower())
            if vol is None or not lib["enabled"]:
                continue
            settings = lib["settings"]
            mountpoint = vol.mountpoint if vol.mounted else None
            if vol.mounted and settings.get("read_only") and vol.mounted_read_only is False and vol.key not in self._rw_lease and vol.key not in self._busy and vol.dev_type != "loop":
                mountpoint = await self._attempt(self._remount(vol, writable=False, settings=settings)) or mountpoint
            elif not vol.mounted and settings.get("auto_mount_library") and time.monotonic() - self._mount_failures.get(vol.key, -MOUNT_RETRY) >= MOUNT_RETRY:
                mountpoint = await self._attempt(self._mount_volume(vol, writable=False, settings=settings))
                if mountpoint is None:
                    self._mount_failures[vol.key] = time.monotonic()
            if mountpoint:
                online[lib["id"]] = mountpoint
        if online == self._online:
            return
        previous = self._online
        availability.set_online({i: p for i, p in online.items() if previous.get(i) == p})

        def _remap() -> bool:
            with SessionLocal() as db:
                return library.apply_mapping(db, online, previous)

        await asyncio.to_thread(_remap)
        self._online = online
        availability.set_online(online)
        from app.utils.ws_manager import manager as ws_manager

        ws_manager.broadcast_threadsafe({"event": "library_change", "reason": "storage_availability"})
        arrived = [i for i in online if i not in previous]
        gone = [i for i in previous if i not in online]
        self.notify("library", (["library_online"] * len(arrived)) + (["library_offline"] * len(gone)))

    async def _attempt(self, coro: Any) -> str | None:
        try:
            return await coro
        except DeviceError as exc:
            logger.info("Stockage externe : %s (%s)", exc.message, exc.code)
        except Exception as exc:
            logger.warning("Stockage externe : %s", exc)
        return None

    def _need(self, key: str, *, format_job: str | None = None) -> Volume:
        vol = self._by_key.get(key)
        if vol is None:
            raise DeviceError("volume_not_found", "Support introuvable : il a peut-être été retiré.", 404)
        active = self.formatter.active()
        formatting_disk = active is not None and vol.disk == active.disk_name
        if (key in self._formatting or formatting_disk) and (active is None or format_job != active.id):
            raise DeviceError("busy", "Ce support est en cours de préparation (formatage) : attendez la fin.", 409)
        return vol

    async def status(self) -> dict[str, Any]:
        caps = await self.driver.capabilities()
        return {
            "driver": self.driver.name,
            "capabilities": caps,
            "ready": self._ready,
            "error": self._last_error,
            "hidden_count": len(self._inventory.excluded),
            "free_local_bytes": await asyncio.to_thread(verified_copy.free_bytes),
        }

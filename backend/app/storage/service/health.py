"""Santé des disques, TRIM et maintenance périodique."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from app.devices.base import DeviceError
from app.storage import health, library
from app.storage.types import Volume

from .constants import HEALTH_TTL, HEALTH_PERIOD, STANDBY_RETRY


class HealthMixin:
    async def health(self, key: str, refresh: bool = False) -> dict[str, Any]:
        vol = self._need(key)
        cached = self._health.get(key)
        if cached and not refresh and time.monotonic() - cached[0] < HEALTH_TTL:
            report = cached[1]
        else:
            report = await self.driver.smart(vol)
            self._health[key] = (time.monotonic(), report)
            self._health_last_run[key] = time.monotonic()
            await self._persist_health(vol, report)
        wear = "ok"
        written = 0
        from app.database import SessionLocal

        def _written() -> int:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                return (lib.bytes_written or 0) if lib else self._written_unregistered.get(key, 0)

        written = await asyncio.to_thread(_written)
        wear = health.write_wear_level(vol.kind, written)
        return {**report, "bytes_written": written, "write_wear": wear, "overall": health.combine_status(report.get("status", "unknown"), wear)}

    async def _persist_health(self, vol: Volume, report: dict[str, Any]) -> None:
        from app.database import SessionLocal

        def _save() -> None:
            with SessionLocal() as db:
                lib = library.get_by_uuid(db, vol.fs_uuid)
                if lib is not None:
                    lib.last_health = json.dumps(report)
                    db.commit()

        await asyncio.to_thread(_save)

    async def trim(self, key: str) -> dict[str, str]:
        vol = self._need(key)
        out = await self.driver.trim(vol)
        self._log("storage_trim", vol.display_name)
        return {"result": out}

    async def _maintenance(self) -> None:
        now = time.monotonic()
        if now - self._last_maintenance < 30:
            return
        self._last_maintenance = now
        facts = await self.driver.facts()
        for key, vol in list(self._by_key.items()):
            if not vol.mounted:
                continue
            settings = await self._effective_settings(vol)
            if settings.get("smart_monitor") and now - self._health_last_run.get(key, -HEALTH_PERIOD) >= HEALTH_PERIOD:
                self._health_last_run[key] = now
                before = (self._health.get(key) or (0, {}))[1].get("status")
                report = await self.driver.smart(vol)
                self._health[key] = (now, report)
                await self._persist_health(vol, report)
                if report.get("available") and report.get("status") in ("warning", "critical") and report.get("status") != before:
                    self._log("storage_health_warning", f"{vol.display_name} : {', '.join(report.get('warnings', []))}")
                    self.notify("health", ["health_warning"])
            minutes = int(settings.get("standby_minutes") or 0)
            if vol.rotational is True and minutes and facts.get("standby_supported") and not self._busy.get(key):
                last = self._activity.get(key, now - 0.0)
                self._activity.setdefault(key, now)
                state = self._standby.get(key)
                if now - last >= minutes * 60 and (state is None or (state.get("ok") is False and now - state.get("mono", 0) >= STANDBY_RETRY) or last > state.get("mono", 0)):
                    try:
                        method = await self.driver.standby(vol)
                        self._standby[key] = {"ok": True, "method": method, "at": datetime.now(timezone.utc).isoformat(), "mono": now}
                    except DeviceError as exc:
                        self._standby[key] = {"ok": False, "error": exc.message, "at": datetime.now(timezone.utc).isoformat(), "mono": now}

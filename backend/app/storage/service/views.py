"""Vue publique des supports, en ligne ou hors ligne."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from app.storage import fsadvisor, health, library, longevity
from app.storage.lsblk import duplicate_uuids, media_for_kind
from app.storage.types import Volume, uuid_key, volume_public


class ViewMixin:
    async def list_volumes(self) -> dict[str, Any]:
        from app.database import SessionLocal

        def _libs() -> list[dict[str, Any]]:
            with SessionLocal() as db:
                out = []
                for lib in library.all_libraries(db):
                    out.append({
                        "id": lib.id, "uuid": lib.fs_uuid, "label": lib.label, "nickname": lib.nickname, "fstype": lib.fstype,
                        "size_bytes": lib.size_bytes, "kind": lib.kind, "enabled": lib.enabled,
                        "bytes_written": lib.bytes_written or 0, "last_seen_at": lib.last_seen_at.isoformat() if lib.last_seen_at else None,
                        "health": json.loads(lib.last_health) if lib.last_health else None,
                        "stats": library.stats(db, lib.id), "settings": library.settings_of(db, lib),
                    })
                return out

        libs = await asyncio.to_thread(_libs)
        by_uuid = {l["uuid"].lower(): l for l in libs}
        duplicates = duplicate_uuids(self._inventory.volumes)
        facts = await self.driver.facts()
        views = [await self._view(v, by_uuid.get((v.fs_uuid or "").lower()), duplicates, facts) for v in self._inventory.volumes]
        connected = {(v.fs_uuid or "").lower() for v in self._inventory.volumes}
        for lib in libs:
            if lib["uuid"].lower() not in connected:
                views.append(self._offline_view(lib))
        return {
            "volumes": views,
            "recent_removals": [{"key": r["key"], "name": r["name"], "abrupt": r["abrupt"]} for r in self._recent],
            "hidden_count": len(self._inventory.excluded),
            "encrypted": [{"name": v.display_name, "fstype": v.fstype} for v in self._inventory.encrypted],
        }

    def _offline_view(self, lib: dict[str, Any]) -> dict[str, Any]:
        return {
            "key": uuid_key(lib["uuid"]),
            "name": lib["nickname"] or lib["label"] or lib["uuid"], "label": lib["label"], "fstype": lib["fstype"],
            "size_bytes": lib["size_bytes"], "kind": lib["kind"], "connected": False, "state": "offline", "mounted": False,
            "mounted_read_only": None, "uuid_known": True, "portable": False, "transport": None, "vendor": None, "model": None,
            "rotational": None, "usage": None, "can_register": False, "register_block": "not_connected",
            "assessment": fsadvisor.assess_filesystem(lib["fstype"], media=media_for_kind(lib["kind"])).as_dict(),
            "library": {
                "registered": True, "id": lib["id"], "nickname": lib["nickname"], "online": False, "stats": lib["stats"],
                "bytes_written": lib["bytes_written"], "wear_level": health.write_wear_level(lib["kind"], lib["bytes_written"]),
                "last_seen_at": lib["last_seen_at"], "settings": lib["settings"],
            },
            "health": lib["health"], "longevity": [], "standby": None,
        }

    async def _view(self, vol: Volume, lib: dict[str, Any] | None, duplicates: set[str], facts: dict[str, Any]) -> dict[str, Any]:
        settings = lib["settings"] if lib else await self._effective_settings(vol)
        state = "formatting" if vol.key in self._formatting else "ejecting" if vol.key in self._ejecting else "busy" if self._busy.get(vol.key) else "mounted" if vol.mounted else "present"
        assessment = fsadvisor.assess_filesystem(vol.fstype, media=media_for_kind(vol.kind), dirty=vol.key in self._dirty)
        usage = None
        if vol.mountpoint:
            try:
                du = await asyncio.to_thread(shutil.disk_usage, vol.mountpoint)
                usage = {"total_bytes": du.total, "free_bytes": du.free}
            except OSError:
                usage = None
        cached = self._health.get(vol.key)
        smart = cached[1] if cached else (lib["health"] if lib else None)
        report = longevity.report(settings, longevity.Facts(
            mounted=vol.mounted, mounted_read_only=vol.mounted_read_only, mount_options=vol.mount_options,
            rotational=vol.rotational, discard_supported=vol.discard_supported, is_root=bool(facts.get("is_root")),
            fstrim_timer_enabled=facts.get("fstrim_timer_enabled"), standby_supported=bool(facts.get("standby_supported")),
            smart_available=(smart or {}).get("available") if smart else None, smart_reason=(smart or {}).get("reason") if smart else None,
        ))
        block = None
        if not vol.fs_uuid:
            block = "uuid_missing"
        elif vol.fs_uuid.lower() in duplicates:
            block = "uuid_duplicate"
        view = volume_public(vol)
        view.update({
            "connected": True, "state": state, "portable": False, "usage": usage, "assessment": assessment.as_dict(),
            "can_register": block is None and not (lib is not None), "register_block": block,
            "library": None, "health": smart, "longevity": report,
            "standby": self._standby.get(vol.key),
        })
        if lib:
            view["library"] = {
                "registered": True, "id": lib["id"], "nickname": lib["nickname"], "online": lib["id"] in self._online,
                "stats": lib["stats"], "bytes_written": lib["bytes_written"],
                "wear_level": health.write_wear_level(vol.kind, lib["bytes_written"]), "last_seen_at": lib["last_seen_at"],
                "settings": lib["settings"],
            }
        else:
            view["library"] = {"registered": False, "settings": settings,
                               "bytes_written": self._written_unregistered.get(vol.key, 0),
                               "wear_level": health.write_wear_level(vol.kind, self._written_unregistered.get(vol.key, 0))}
        return view

    def volume(self, key: str) -> Volume | None:
        return self._by_key.get(key)
